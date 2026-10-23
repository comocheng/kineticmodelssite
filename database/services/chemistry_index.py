"""Fill the shared chemical identity: structure keys, reaction keys and layers, rate fingerprints.

Bulk functions backfill everything that is missing (or everything, with refresh=True); the
single-row functions keep new imports indexed. All computation is local; no network calls.
"""
from collections import defaultdict

from database.models import Isomer, Kinetics, Reaction, Species, SpeciesName, Stoichiometry, Structure
from database.services.chemical_identity import (
    rate_fingerprint, reaction_key, reaction_layer, species_key, structure_key,
)

BATCH = 1000


def _flush(model, rows, fields):
    if rows:
        model.objects.bulk_update(rows, fields)
    return []


def index_structures(refresh=False):
    structures = Structure.objects.all() if refresh else Structure.objects.filter(structure_key="")
    pending, done = [], 0
    for structure in structures.iterator(chunk_size=BATCH):
        try:
            structure.structure_key = structure_key(structure.to_rmg())
        except Exception:
            continue
        pending.append(structure)
        done += 1
        if len(pending) >= BATCH:
            pending = _flush(Structure, pending, ["structure_key"])
    _flush(Structure, pending, ["structure_key"])
    return done


def species_tables(species_ids=None):
    """species id -> species key, and species id -> formula of its first isomer."""
    links = Species.isomers.through.objects.all()
    if species_ids is not None:
        links = links.filter(species_id__in=species_ids)
    isomers_of = defaultdict(list)
    for species_id, isomer_id in links.values_list("species_id", "isomer_id"):
        isomers_of[species_id].append(isomer_id)
    isomer_ids = {isomer for isomers in isomers_of.values() for isomer in isomers}
    keys_of_isomer = defaultdict(list)
    for isomer_id, key in Structure.objects.filter(isomer_id__in=isomer_ids).values_list("isomer_id", "structure_key"):
        keys_of_isomer[isomer_id].append(key)
    formula_of_isomer = dict(Isomer.objects.filter(id__in=isomer_ids).values_list("id", "formula__formula"))
    keys, formulas = {}, {}
    for species_id, isomers in isomers_of.items():
        structure_keys = [key for isomer in isomers for key in keys_of_isomer.get(isomer, [])]
        # A species with an unkeyed structure has no reliable identity yet.
        keys[species_id] = species_key(structure_keys) if structure_keys and all(structure_keys) else ""
        formulas[species_id] = formula_of_isomer.get(min(isomers))
    return keys, formulas


def describe_reaction(rows, keys, formulas):
    """(canonical_key, canonical_direction, layer) from (species id, coefficient) rows."""
    reactant_species = {species for species, coeff in rows if coeff < 0}
    product_species = {species for species, coeff in rows if coeff > 0}
    reactants = [keys.get(species, "") for species, coeff in rows if coeff < 0 for _ in range(int(round(-coeff)))]
    products = [keys.get(species, "") for species, coeff in rows if coeff > 0 for _ in range(int(round(coeff)))]
    key, direction = reaction_key(reactants, products)
    # An explicit collider (H2 + AR = H + H + AR) sits on both sides; it says nothing about the layer.
    colliders = reactant_species & product_species
    chemistry = [formulas.get(species) for species, _ in rows if species not in colliders] or \
                [formulas.get(species) for species, _ in rows]
    return key, direction, reaction_layer(formula for formula in chemistry if formula)


def index_reactions(refresh=False):
    keys, formulas = species_tables()
    rows_of = defaultdict(list)
    for reaction_id, species_id, coeff in Stoichiometry.objects.values_list("reaction_id", "species_id", "coeff"):
        rows_of[reaction_id].append((species_id, coeff))
    reactions = Reaction.objects.all() if refresh else Reaction.objects.filter(canonical_direction=0)
    fields = ["canonical_key", "canonical_direction", "layer"]
    pending, done = [], 0
    for reaction in reactions.only("id", *fields).iterator(chunk_size=BATCH):
        key, direction, layer = describe_reaction(rows_of[reaction.id], keys, formulas)
        reaction.canonical_key, reaction.canonical_direction, reaction.layer = key, direction, layer
        pending.append(reaction)
        done += 1
        if len(pending) >= BATCH:
            pending = _flush(Reaction, pending, fields)
    _flush(Reaction, pending, fields)
    return done


def index_reaction(reaction):
    rows = list(reaction.stoichiometry_set.values_list("species_id", "coeff"))
    keys, formulas = species_tables({species for species, _ in rows})
    reaction.canonical_key, reaction.canonical_direction, reaction.layer = describe_reaction(rows, keys, formulas)
    reaction.save(update_fields=["canonical_key", "canonical_direction", "layer"])
    return reaction


def kinetics_fingerprint(kinetics):
    """Fingerprint without collider efficiencies, which don't change k at the default mixture.
    [] marks kinetics that cannot be evaluated, so they are not retried every run."""
    try:
        rmg = kinetics.data.to_rmg(kinetics.min_temp, kinetics.max_temp,
                                   kinetics.min_pressure, kinetics.max_pressure, [])
    except Exception:
        return []
    return rate_fingerprint(rmg) or []


def index_kinetics(refresh=False):
    rows = Kinetics.objects.all() if refresh else Kinetics.objects.filter(rate_fingerprint__isnull=True)
    pending, done = [], 0
    for kinetics in rows.only("id", "raw_data", "min_temp", "max_temp", "min_pressure", "max_pressure",
                              "rate_fingerprint").iterator(chunk_size=BATCH):
        kinetics.rate_fingerprint = kinetics_fingerprint(kinetics)
        pending.append(kinetics)
        done += 1
        if len(pending) >= BATCH:
            pending = _flush(Kinetics, pending, ["rate_fingerprint"])
    _flush(Kinetics, pending, ["rate_fingerprint"])
    return done


def equations(reaction_models):
    """{reaction id: model id or None} -> {reaction id: equation}, in that model's species names
    where it has them and formulas otherwise. A few queries for any number of reactions."""
    sides = defaultdict(list)
    for reaction_id, species_id, coeff in Stoichiometry.objects.filter(
            reaction_id__in=reaction_models).values_list("reaction_id", "species_id", "coeff"):
        sides[reaction_id].append((species_id, coeff))
    species_ids = {s for rows in sides.values() for s, _ in rows}
    _, formulas = species_tables(species_ids)
    names = {(s, m): name for s, m, name in SpeciesName.objects.filter(
        species_id__in=species_ids, kinetic_model_id__in={m for m in reaction_models.values() if m}).exclude(name="").values_list(
        "species_id", "kinetic_model_id", "name")}

    def side(reaction_id, keep):
        terms = []
        for species_id, coeff in sides[reaction_id]:
            if keep(coeff):
                label = names.get((species_id, reaction_models[reaction_id])) or formulas.get(species_id) or f"#{species_id}"
                count = abs(coeff)
                terms.append(label if count in (0, 1) else f"{count:g} {label}")
        return " + ".join(terms)
    return {r: f"{side(r, lambda c: c <= 0)} = {side(r, lambda c: c >= 0)}" for r in reaction_models}
