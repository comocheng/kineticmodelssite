import logging
import math
import os
import re
import hashlib
from collections import ChainMap, defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import habanero
from django.db import transaction, IntegrityError
from dateutil import parser
from rmgpy import kinetics, constants
from rmgpy.chemkin import read_kinetics_entry
from rmgpy.quantity import RateCoefficient
from rmgpy.reaction import Reaction
from rmgpy.species import Species
from database.scripts import chemkin_lines
from database.scripts.rmg_libraries import (
    TolerantKineticsLibrary, TolerantThermoLibrary, smiles_txt_states, structure_key_or_none)
from rmgpy.thermo import NASA, ThermoData, Wilhoit, NASAPolynomial

from django.conf import settings
from database.models import kinetic_data as kd
from database.services.chemical_identity import structure_key


"""
Import Flow:
* Kinetic Model: update CharFields
* Source: update CharFields & Authors
* Thermo (Entry): update thermo data (coeffs, reference state) & source
* Kinetics: update prime_id, source, uncertainty, data, & reaction prime_id
1. Kinetic Model
    * Get or Create Kinetic Model with RMG-model name
    * Update fields available in RMG-models
    * Import Sources
    * Import Thermo
    * Import Kinetics
2. Sources:
    * Get as many fields as possible
    * Get or create the Source
    * Try to save Source (errors: blank required fields -> response: skip)
    * Get author data
    * Get or create Authors
    * Create Authorships
    * Try to save Authorships (errors: no author data -> response: keep source but no authors)

3. Thermo:
    * Load thermo library (errors: fails -> response: skip)
    * Get the Species (errors: no species -> response: skip)
    * Get as many fields as possible
    * Try to save Thermo (errors: blank required fields -> response: skip)
    * Create the Species Isomers & Structures (errors: no/missing isomers/structures -> response: keep species & skip missing)
    * Link Species and save
"""  # noqa: E501

logger = logging.getLogger(__name__)

if getattr(settings, "SILENCE_RMG_IMPORT_LOGS", False):
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False
else:
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename="importer.log", mode="w")
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False


def safe_import(func, *args, error_message=None, **kwargs):
    try:
        with transaction.atomic():
            func(*args, **kwargs)
    except Exception:
        message = error_message or f"Failed to execute {func.__name__}"
        logger.exception(message)


def import_rmg_models(apps, schema_editor):
    model_names = [
        "KineticModel",
        "Source",
        "Author",
        "Authorship",
        "Thermo",
        "ThermoComment",
        "Species",
        "Formula",
        "Isomer",
        "Structure",
        "SpeciesName",
        "Efficiency",
        "Kinetics",
        "KineticsComment",
        "Reaction",
        "Stoichiometry",
    ]
    models = SimpleNamespace()
    logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for name in model_names:
        setattr(models, name, apps.get_model("database", name))
    path = os.getenv("RMGMODELSPATH", "./rmg-models/")


    skip_list = ["PCI2011/193-Mehl"]
    model_paths = get_models(path, skip_list)

    for rmg_model_name, thermo_path, kinetics_path, source_path in model_paths:
        logger.info(f"IMPORTING KINETIC MODEL: {rmg_model_name}")
        safe_import(
            import_kinetic_model, rmg_model_name, thermo_path, kinetics_path, source_path, models
        )


def import_kinetic_model(rmg_model_name, thermo_path, kinetics_path, source_path, models):
    now = datetime.now()
    kinetic_model, created = models.KineticModel.objects.get_or_create(
        model_name=rmg_model_name,
        defaults={"info": f"Imported via RMG-models migration at {now.isoformat()}"},
    )
    if not created:
        # Keep the import idempotent: update the info timestamp but don't crash.
        kinetic_model.info = f"Re-imported via RMG-models migration at {now.isoformat()}"
        kinetic_model.save(update_fields=["info"])
    logger.info(f"Importing Source {source_path}")
    safe_import(import_source, source_path, kinetic_model, models)
    logger.info(f"Importing Thermo Library {thermo_path}")
    safe_import(import_thermo, thermo_path, kinetic_model, models)
    logger.info(f"Importing Kinetics Library {kinetics_path}")
    safe_import(import_kinetics, kinetics_path, kinetic_model, models)


def safe_save(instance):
    try:
        instance.save()
        return instance
    except Exception:
        logger.exception(f"Error when saving instance of {instance.__class__.__qualname__}")


def filter_fields(fields, filter_value=None):
    return {k: v for k, v in fields.items() if v != filter_value}


def get_species_hash(isomers, electronic_state=""):
    isomer_fingerprint = "".join(sorted(set(str(isomer.id) for isomer in isomers)))
    if electronic_state:
        # An excited state has the same isomers as the ground state.
        isomer_fingerprint += f"@{electronic_state}"

    return hashlib.md5(bytes(isomer_fingerprint, "UTF-8")).hexdigest()


def get_or_create_species(kinetic_model, name, molecules, models, electronic_state=""):
    formula = molecules[0].get_formula()
    formula_obj, _ = models.Formula.objects.get_or_create(formula=formula)
    isomers = []
    for molecule in molecules:
        smiles = molecule.to_smiles()
        augmented_inchi = molecule.to_augmented_inchi()
        adjacency_list = molecule.to_adjacency_list()
        multiplicity = molecule.multiplicity
        isomer, _ = models.Isomer.objects.get_or_create(inchi=augmented_inchi, formula=formula_obj)
        isomers.append(isomer)

        # Deduplicate by molecular graph isomorphism, not just adjacency
        # list text.  Different atom numberings produce different text but
        # represent the same molecule.
        existing = models.Structure.objects.filter(
            isomer=isomer, multiplicity=multiplicity,
        )
        match = None
        for candidate in existing:
            try:
                if candidate.to_rmg().is_isomorphic(molecule):
                    match = candidate
                    break
            except Exception:
                continue
        if match is None:
            models.Structure.objects.get_or_create(
                adjacency_list=adjacency_list,
                defaults={"smiles": smiles, "multiplicity": multiplicity, "isomer": isomer},
            )

    species = species_record(isomers, molecules, models, electronic_state)
    add_species_name(species, kinetic_model, name, models)

    return species


def molecule_key(molecule):
    """The structure key, or None when RMG cannot make an InChIKey for the molecule."""
    try:
        return structure_key(molecule)
    except Exception:
        return None


def has_field(model, name):
    """False for the historical models of old data migrations, which predate newer fields."""
    return any(field.name == name for field in model._meta.get_fields())


def has_structure_keys(models):
    return has_field(models.Structure, "structure_key")


def new_species(isomers, models, electronic_state):
    if not has_field(models.Species, "electronic_state"):
        species, created = models.Species.objects.get_or_create(hash=get_species_hash(isomers))
    else:
        species, created = models.Species.objects.get_or_create(
            hash=get_species_hash(isomers, electronic_state), defaults={"electronic_state": electronic_state})
    if created:
        species.isomers.add(*isomers)
    return species


def species_record(isomers, molecules, models, electronic_state=""):
    """The one species record for these molecules in this electronic state.

    A thermo entry gives one resonance form of a radical and a reaction gives all of them, so
    the isomer sets differ. The record is therefore found by structure key (InChIKey plus
    multiplicity: different for spin states) or by a shared isomer, and missing resonance forms
    are added to it. Resonance forms usually share one key, but not when their InChI H layers
    differ ([CH2]C(=O)O and C=C([O])O), so a record that holds any of the keys is a candidate.
    An excited state (OH*) has the structures of its ground state, so the electronic state is
    part of the identity too. A model's second name for a structure (furop2 next to furop1) is a
    second name of this record (see model_repeats). The hash stays the isomer-set fingerprint
    plus the state (signals.py keeps it current).
    """
    if not has_structure_keys(models):
        # Old data migrations: their historical models have no structure keys.
        return new_species(isomers, models, electronic_state)
    keys = {molecule_key(molecule) for molecule in molecules} - {None}

    # Simple indexed lookups: isomers with these structure keys, then the species that hold
    # any of them, then all isomers of those species.
    isomer_ids = {isomer.id for isomer in isomers}
    keyed = set(models.Structure.objects.filter(structure_key__in=keys)
                .values_list("isomer_id", flat=True))
    links = models.Species.isomers.through.objects
    species_ids = set(links.filter(isomer_id__in=isomer_ids | keyed)
                      .values_list("species_id", flat=True))
    candidates = models.Species.objects.filter(pk__in=species_ids)
    if has_field(models.Species, "electronic_state"):
        candidates = candidates.filter(electronic_state=electronic_state)
    candidates = list(candidates)
    isomers_of = defaultdict(set)
    for species_id, isomer_id in links.filter(species_id__in=[s.pk for s in candidates]) \
            .values_list("species_id", "isomer_id"):
        isomers_of[species_id].add(isomer_id)
    held = {species: isomers_of[species.pk] for species in candidates}
    if not held:
        return new_species(isomers, models, electronic_state)
    # Older imports left one record per resonance set. Prefer a record that already holds
    # every form here, then the most complete record, then the oldest.
    covering = [s for s, ids in held.items() if isomer_ids <= ids]
    species = min(covering or held, key=lambda s: (-len(held[s]), s.pk))
    missing = [isomer for isomer in isomers if isomer.id not in held[species]]
    if missing:
        species.isomers.add(*missing)
    return species


def add_species_name(species, kinetic_model, name, models):
    """Record what the kinetic model calls this species.

    An empty name only links a species to the model until its label is known: it is never
    written next to a real name, and a real name replaces it.
    """
    names = models.SpeciesName.objects.filter(species=species, kinetic_model=kinetic_model)
    if not name:
        if not names.exists():
            models.SpeciesName.objects.create(name="", species=species, kinetic_model=kinetic_model)
        return
    if not names.filter(name=name).exists():
        placeholder = names.filter(name="").order_by("pk").first()
        if placeholder is None:
            models.SpeciesName.objects.create(
                name=name, species=species, kinetic_model=kinetic_model)
        else:
            placeholder.name = name
            placeholder.save(update_fields=["name"])
    names.filter(name="").delete()


def get_reaction_hash(stoich_data):
    reaction_fingerprint = "".join(
        sorted(set(f"{stoich:.4f}{species.id}" for stoich, species in stoich_data))
    )

    return hashlib.md5(bytes(reaction_fingerprint, "UTF-8")).hexdigest()


def index_new_rows(models, reaction=None, kinetics=None):
    """Keep the shared chemical identity current for new rows. Skipped when an old data
    migration runs this importer with historical models, which lack these fields."""
    from database.models import Reaction
    if getattr(models, "Reaction", None) is not Reaction:
        return
    from database.services import chemistry_index
    if reaction is not None:
        chemistry_index.index_reaction(reaction)
    if kinetics is not None:
        kinetics.rate_fingerprint = chemistry_index.kinetics_fingerprint(kinetics)
        kinetics.save(update_fields=["rate_fingerprint"])


def labelled_species(kinetic_model, rmg_species, models, states=None, cache=None):
    """The species record of a species of the library dictionary: a reactant, a product or a
    specific collider. The label is the species name in the mechanism; `states` and `cache`
    are those of get_or_create_reaction."""
    name = rmg_species.label
    state = (states or {}).get(name, "")
    key = ("label", name, state) if name and cache is not None else None
    species = cache.get(key) if key else None
    if species is None:
        species = get_or_create_species(
            kinetic_model, name or "", rmg_species.molecule, models, electronic_state=state)
        if key:
            cache[key] = species
    return species


def get_or_create_reaction(kinetic_model, rmg_reaction, models, states=None, cache=None):
    """
    Create and save a reaction from an RMG reaction

    The kinetic model argument is needed to create species that are not yet in the database.
    If a reaction already exists, it is looked up and returned.
    The uniqueness of a reaction consists of a set of species
    and respective stoichiometric coefficients.
    `states` maps species labels to electronic states (see model_states). `cache` (a dict,
    kept for one library import) maps a label and state to its species record, so a species
    that takes part in many reactions is looked up once.
    """

    reversible = rmg_reaction.reversible
    reactants = rmg_reaction.reactants
    products = rmg_reaction.products
    reaction_species = [*reactants, *products]
    stoich_data = []
    species_map = {}
    for s in reaction_species:
        name = s.label
        if species_map.get(name) is None:
            species_map[name] = s

    with transaction.atomic():
        # Two names of one record on one side (furop1 + furop2) add up to one coefficient.
        coefficients = {}
        for name, rmg_species in species_map.items():
            species = labelled_species(kinetic_model, rmg_species, models, states, cache)
            reactant_coeff = sum(-1 for reactant in reactants if reactant == rmg_species)
            product_coeff = sum(1 for product in products if product == rmg_species)
            for coeff in (reactant_coeff, product_coeff):
                if coeff != 0:
                    total = coefficients.get((species.pk, coeff < 0), (0, species))[0] + coeff
                    coefficients[(species.pk, coeff < 0)] = (total, species)
        stoich_data = list(coefficients.values())

        reaction, created = models.Reaction.objects.get_or_create(
            hash=get_reaction_hash(stoich_data=stoich_data), defaults={"reversible": reversible}
        )
        if created:
            for stoich_coeff, species in stoich_data:
                models.Stoichiometry.objects.create(
                    reaction=reaction, species=species, coeff=stoich_coeff
                )
            index_new_rows(models, reaction=reaction)

        stoich_reactants = reaction.stoichiometry_set.filter(coeff__lte=0)
        stoich_products = reaction.stoichiometry_set.filter(coeff__gte=0)
        if not (stoich_reactants or stoich_products):
            reactants_or_products = "reactants" if not stoich_reactants else "products"
            raise IntegrityError(f"Reaction cannot have zero {reactants_or_products}")

    return reaction


def create_arrhenius(rmg_kinetics_data):
    return kd.Arrhenius(
        type="arrhenius",
        a=rmg_kinetics_data.A.value,
        a_si=rmg_kinetics_data.A.value_si,
        a_units=rmg_kinetics_data.A.units,
        n=rmg_kinetics_data.n.value_si,
        e=rmg_kinetics_data.Ea.value,
        e_si=rmg_kinetics_data.Ea.value_si,
        e_units=rmg_kinetics_data.Ea.units,
    )


def create_arrhenius_ep(rmg_kinetics_data):
    return kd.ArrheniusEP(
        type="arrhenius_ep",
        a=rmg_kinetics_data.A.value,
        a_si=rmg_kinetics_data.A.value_si,
        a_units=rmg_kinetics_data.A.units,
        n=rmg_kinetics_data.n.value_si,
        alpha=rmg_kinetics_data.alpha.value_si,
        e0=rmg_kinetics_data.E0.value,
        e0_si=rmg_kinetics_data.E0.value_si,
        e0_units=rmg_kinetics_data.E0.units,
    )


def create_multi_arrhenius(rmg_kinetics_data):
    return kd.MultiArrhenius(
        type="multi_arrhenius",
        arrhenius_set=[
            create_arrhenius(rmg_arrhenius) for rmg_arrhenius in rmg_kinetics_data.arrhenius
        ],
    )


def create_pdep_arrhenius(rmg_kinetics_data):
    return kd.PDepArrhenius(
        type="pdep_arrhenius",
        pressure_set=[
            kd.Pressure(arrhenius=create_multi_arrhenius(a) if isinstance(a, kinetics.MultiArrhenius)
                        else create_arrhenius(a), pressure=p)
            for p, a in zip(rmg_kinetics_data.pressures.value_si, rmg_kinetics_data.arrhenius)
        ],
    )


def create_multi_pdep_arrhenius(rmg_kinetics_data):
    return kd.MultiPDepArrhenius(
        type="multi_pdep_arrhenius",
        pdep_arrhenius_set=[create_pdep_arrhenius(a) for a in rmg_kinetics_data.arrhenius],
    )


def create_chebyshev(rmg_kinetics_data):
    # RMG adds log10 of the kunits-to-SI factor to coeffs[0, 0]; store them as written, in kunits.
    coeffs = rmg_kinetics_data.coeffs.value_si.copy()
    coeffs[0, 0] -= math.log10(RateCoefficient(1.0, rmg_kinetics_data.kunits).value_si)
    return kd.Chebyshev(
        type="chebyshev",
        coefficient_matrix=coeffs.tolist(),
        units=rmg_kinetics_data.kunits,
    )


def create_third_body(rmg_kinetics_data):
    return kd.ThirdBody(
        type="third_body",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
    )


def create_lindemann(rmg_kinetics_data):
    return kd.Lindemann(
        type="lindemann",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
        high_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusHigh),
    )


def create_troe(rmg_kinetics_data):
    troe_fields = filter_fields(
        {
            "t1": rmg_kinetics_data.T1.value_si if rmg_kinetics_data.T1 is not None else None,
            "t2": rmg_kinetics_data.T2.value_si if rmg_kinetics_data.T2 is not None else None,
            "t3": rmg_kinetics_data.T3.value_si if rmg_kinetics_data.T3 is not None else None,
        }
    )
    return kd.Troe(
        type="troe",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
        high_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusHigh),
        alpha=rmg_kinetics_data.alpha,
        **troe_fields,
    )


def create_general_kinetics_data(rmg_kinetics_data):
    return kd.KineticsData(
        type="kinetics_data",
        temps=rmg_kinetics_data.Tdata,
        rate_coeffs=rmg_kinetics_data.kdata,
    )


def labels_by_structure_key(species_dict, states=None, repeats=None):
    """Structure key -> label for the ground-state species of a library dictionary.

    Collider efficiencies are written as SMILES, so this is how their species get the
    mechanism's name. A SMILES is a ground state, so excited labels (OH*) are left out; a key
    shared by two ground-state labels names neither. A model's later name for a structure
    (furop2, see model_repeats) is left out too, so the key names the first one.
    """
    labels = {}
    for label, rmg_species in (species_dict or {}).items():
        if (states or {}).get(label) or label in (repeats or {}):
            continue
        for key in {molecule_key(molecule) for molecule in rmg_species.molecule} - {None}:
            labels[key] = None if labels.get(key, label) != label else label
    return {key: label for key, label in labels.items() if label}


def collider_efficiencies(kinetic_model, rmg_kinetics_data, models, labels=None, cache=None):
    """(species record, efficiency) for each collider efficiency of a library entry; none for
    PLOG and Chebyshev kinetics. `labels` is labels_by_structure_key, `cache` that of
    import_kinetics."""
    efficiencies = []
    for rmg_molecule, efficiency in (getattr(rmg_kinetics_data, "efficiencies", None) or {}).items():
        structure = molecule_key(rmg_molecule)
        name = (labels or {}).get(structure, "")
        # A labelled collider is the reaction species with that label (ground state).
        key = None
        if cache is not None:
            key = ("label", name, "") if name else (("structure", structure) if structure else None)
        species = cache.get(key) if key else None
        if species is None:
            species = get_or_create_species(kinetic_model, name, [rmg_molecule], models)
            if key:
                cache[key] = species
        efficiencies.append((species, efficiency))
    return efficiencies


def get_base_kinetics_data_fields(rmg_kinetics_data):
    return filter_fields(
        {
            "min_temp": rmg_kinetics_data.Tmin.value_si
            if rmg_kinetics_data.Tmin is not None
            else None,
            "max_temp": rmg_kinetics_data.Tmax.value_si
            if rmg_kinetics_data.Tmax is not None
            else None,
            "min_pressure": rmg_kinetics_data.Pmin.value_si
            if rmg_kinetics_data.Pmin is not None
            else None,
            "max_pressure": rmg_kinetics_data.Pmax.value_si
            if rmg_kinetics_data.Pmax is not None
            else None,
        }
    )


def create_kinetics_data(kinetic_model, rmg_kinetics_data, models):
    kinetics_factory = {
        "KineticsData": create_general_kinetics_data,
        "Arrhenius": create_arrhenius,
        "ArrheniusEP": create_arrhenius_ep,
        "MultiArrhenius": create_multi_arrhenius,
        "PDepArrhenius": create_pdep_arrhenius,
        "MultiPDepArrhenius": create_multi_pdep_arrhenius,
        "Chebyshev": create_chebyshev,
        "ThirdBody": create_third_body,
        "Lindemann": create_lindemann,
        "Troe": create_troe,
    }
    model_name = rmg_kinetics_data.__class__.__name__
    kinetics_data = kinetics_factory[model_name](rmg_kinetics_data).dict()

    return kinetics_data


def kinetics_local_context():
    """The names an RMG-format reactions.py may use for its kinetics."""
    return {
        "KineticsData": kinetics.KineticsData,
        "Arrhenius": kinetics.Arrhenius,
        "ArrheniusEP": kinetics.ArrheniusEP,
        "MultiArrhenius": kinetics.MultiArrhenius,
        "MultiPDepArrhenius": kinetics.MultiPDepArrhenius,
        "PDepArrhenius": kinetics.PDepArrhenius,
        "Chebyshev": kinetics.Chebyshev,
        "ThirdBody": kinetics.ThirdBody,
        "Lindemann": kinetics.Lindemann,
        "Troe": kinetics.Troe,
        "R": constants.R,
    }


def model_states(library_path):
    """label -> electronic state declared in the model's SMILES.txt (the `excited` prefix).

    The RMG-Py libraries sit in <model>/RMG-Py-*-library/, and SMILES.txt in <model>/.
    """
    return smiles_txt_states(os.path.dirname(os.path.dirname(os.path.abspath(library_path))))


def load_thermo_library(thermo_path, label, states=None):
    """The model's thermo library as TolerantThermoLibrary loads it; `states` as import_thermo."""
    library = TolerantThermoLibrary(label=label)
    library.declared_states = model_states(thermo_path) if states is None else states
    library.load(thermo_path, local_context={
        "ThermoData": ThermoData, "Wilhoit": Wilhoit, "NASAPolynomial": NASAPolynomial, "NASA": NASA})
    return library


# Thermo path, file stamp and states -> TolerantThermoLibrary.repeats, so the kinetics import
# of a model does not load its thermo library again.
_thermo_repeats = {}


def _repeats_key(thermo_path, states):
    stat = os.stat(thermo_path)
    return (os.path.abspath(thermo_path), stat.st_mtime_ns, stat.st_size,
            tuple(sorted((states or {}).items())) if states is not None else None)


def model_repeats(library_path, kinetic_model, states=None):
    """later label -> first label for the structures the model's thermo library lists more than
    once (TolerantThermoLibrary.repeats); {} for a model without a thermo library.

    Both labels are names of one species record. Each keeps its own thermo entry (its thermo
    link names it), and a rate that writes the later label (furop2 + H, after furop1) names it
    (KineticsCommentName). `library_path` is any RMG-Py library of the model."""
    model_dir = os.path.dirname(os.path.dirname(os.path.abspath(library_path)))
    thermo_path = os.path.join(model_dir, "RMG-Py-thermo-library", "ThermoLibrary.py")
    if not os.path.exists(thermo_path):
        return {}
    key = _repeats_key(thermo_path, states)
    if key not in _thermo_repeats:
        _thermo_repeats[key] = dict(load_thermo_library(thermo_path, kinetic_model.model_name, states).repeats)
    return _thermo_repeats[key]


def _names_key(reactants, products):
    return tuple(sorted(tuple(sorted(n.upper() for n in side)) for side in (reactants, products)))


def _combined(terms, kinetics_data):
    """One rate term as it is, several as the kind of multi-rate they came from."""
    if len(terms) == 1:
        return terms[0]
    if isinstance(kinetics_data, kinetics.MultiPDepArrhenius):
        return kinetics.MultiPDepArrhenius(arrhenius=terms, Tmin=kinetics_data.Tmin, Tmax=kinetics_data.Tmax,
                                           Pmin=kinetics_data.Pmin, Pmax=kinetics_data.Pmax)
    return kinetics.MultiArrhenius(arrhenius=terms, Tmin=kinetics_data.Tmin, Tmax=kinetics_data.Tmax)


def _term_rate(term):
    """(A in the written units, n, Ea in J/mol) of an Arrhenius term, or of the first pressure of a
    PDepArrhenius term (as a CHEMKIN PLOG line writes it), and whether it is the latter."""
    if isinstance(term, kinetics.PDepArrhenius):
        first = term.arrhenius[0]
        if isinstance(first, kinetics.MultiArrhenius):
            first = first.arrhenius[0]
        return _term_rate(first)[0], True
    if isinstance(term, kinetics.Arrhenius):
        return (term.A.value, term.n.value_si, term.Ea.value_si), False
    return None, False


def _line_rates(line):
    """A CHEMKIN line's rate as _rates gives a library rate's."""
    if line["plog"] is not None:
        return [line["plog"]]
    rate = (line["A"], line["n"], line["Ea"])
    return [rate, line["low"]] if line["low"] is not None else [rate]


def _rates(kinetics_data):
    """Each rate of a library entry as a CHEMKIN line writes it: a list per term of a multi-rate,
    of (A in the written units, n, Ea in J/mol), the low-pressure rate after the high-pressure one
    for a fall-off rate. None for a kind the lines cannot be compared with (Chebyshev)."""
    if isinstance(kinetics_data, (kinetics.MultiArrhenius, kinetics.MultiPDepArrhenius)):
        terms = [_rates(term) for term in kinetics_data.arrhenius]
        return None if None in terms else [term[0] for term in terms]
    if isinstance(kinetics_data, (kinetics.Lindemann, kinetics.Troe)):
        high, low = (_term_rate(a)[0] for a in (kinetics_data.arrheniusHigh, kinetics_data.arrheniusLow))
        return [[high, low]] if None not in (high, low) else None
    if isinstance(kinetics_data, kinetics.ThirdBody):
        low = _term_rate(kinetics_data.arrheniusLow)[0]
        return [[low]] if low is not None else None
    rate = _term_rate(kinetics_data)[0]
    return [[rate]] if rate is not None else None


def _collider(rmg_reaction, kinetics_data):
    """A library entry's collider as read_reactions gives a CHEMKIN line's, in upper case."""
    specific = getattr(rmg_reaction, "specific_collider", None)
    if specific is not None:
        return specific.label.upper()
    return "M" if isinstance(kinetics_data, (kinetics.ThirdBody, kinetics.Lindemann, kinetics.Troe)) else None


class MergedRates:
    """Gives each rate term of a merged library entry back to the reaction its CHEMKIN line writes.

    Where two of a model's names had one SMILES, RMG-models wrote both names' reactions as one
    entry, labelled with one name: a MultiArrhenius (or MultiPDepArrhenius) with one term per
    CHEMKIN line. Read as written, the labelled name would have both rates and the other name
    neither. Each term is matched to its line in the model's CHEMKIN file (the same species
    structures, the same A, n and Ea); a term from a line of other names (a later name, see
    model_repeats, or another electronic state) becomes that line's rate, with its names.

    Where the model writes an irreversible reaction in both directions, RMG-models kept one entry:
    with both lines' terms (MatheuCH4 entry 785, C.C*CC#CC => C*CC.C#CC, holds line 1644, the
    reverse) or with one line's rate (CombFlame2013/2319-Serinyel CH4 (+CH4) => R4CH3 + R1H (+CH4),
    line 2997, without line 2987, its reverse, and line 2992, its (+M) twin). A term from a line in
    the other direction becomes that line's reaction too, and dropped_lines reads the lines the
    library lacks from the CHEMKIN file. RMG-models is only read."""

    def __init__(self, kinetics_path, library, states, repeats):
        self.lines, self.twins, self.used, self.moved, self.unread = {}, {}, set(), 0, []
        # A later name is told apart from the first name of its structure by the name itself.
        self.states, self.later = states or {}, {later: later for later in (repeats or {})}
        self._keys, self._colliders = {}, None
        species = dict(getattr(library, "species_dict", None) or {})
        self.model_dir = model_dir = os.path.dirname(os.path.dirname(os.path.abspath(kinetics_path)))
        path = chemkin_lines.reactions_file(model_dir)
        if not (path and species):
            return
        for later, first in (repeats or {}).items():
            # A name the kinetics dictionary leaves out (it keeps one label per molecule): the later
            # one (MatheuCH4 MECY24PD) or the first (Atef NC6H13COC2H3, with C6H13COC2H3 kept).
            for missing, present in ((later, first), (first, later)):
                if missing not in species and present in species:
                    species[missing] = Species(label=missing, molecule=species[present].molecule)
        self.species = species
        self.spelling = spelling = {name.upper(): name for name in species}
        tokens = set(spelling) | chemkin_lines.species_names(path)
        ea_to_j, self.molecules = chemkin_lines.units(path, kinetics_path)
        self.units = chemkin_lines.rmg_units(ea_to_j, self.molecules)
        for line in chemkin_lines.read_reactions(path, tokens, ea_to_j):
            names = line["reactants"] + line["products"]
            if not all(n.upper() in spelling for n in names):
                continue
            line["reactants"] = [spelling[n.upper()] for n in line["reactants"]]
            line["products"] = [spelling[n.upper()] for n in line["products"]]
            key = self.key(line["reactants"], line["products"])
            if key is None:
                continue
            if not line["third_body"]:
                self.lines.setdefault(key, []).append(line)
            if not line["reversible"]:
                self.twins.setdefault(key, []).append(line)

    def key(self, reactants, products):
        """The reaction's species structures, either direction; None if one has no key."""
        sides = []
        for side in (reactants, products):
            keys = []
            for name in side:
                if name not in self._keys:
                    found = self.species.get(name)
                    self._keys[name] = structure_key_or_none(found.molecule[0]) if found else None
                if self._keys[name] is None:
                    return None
                keys.append(self._keys[name])
            sides.append(tuple(sorted(keys)))
        return tuple(sorted(sides))

    def identity(self, reactants, products):
        """What tells species of one structure apart: each name's electronic state, and a later
        name."""
        side = lambda names: tuple(sorted((self.states.get(n, ""), self.later.get(n, "")) for n in names))
        return tuple(sorted((side(reactants), side(products))))

    def direction(self, reactants, products):
        """The reactants' species, then the products': A => B and B => A differ."""
        side = lambda names: tuple(sorted((self._keys.get(n), self.states.get(n, ""), self.later.get(n, ""))
                                          for n in names))
        return side(reactants), side(products)

    def parts(self, entry):
        """[(RMG reaction, kinetics, comment)] to import for the entry: the entry itself, or its own
        terms and one part for each other CHEMKIN reaction its terms came from: a line of other
        names or a line in the other direction."""
        data = entry.data
        whole = [(entry.item, data, entry.short_desc)]
        if not self.lines or not isinstance(data, (kinetics.MultiArrhenius, kinetics.MultiPDepArrhenius)):
            return whole
        labels = ([s.label for s in entry.item.reactants], [s.label for s in entry.item.products])
        candidates = self.lines.get(self.key(*labels), [])
        if not candidates:
            return whole
        own_names, own_identity, own_direction = _names_key(*labels), self.identity(*labels), self.direction(*labels)
        own, other = [], {}
        for term in data.arrhenius:
            rate, pdep = _term_rate(term)
            hits = [line for line in candidates if id(line) not in self.used and rate is not None
                    and (line["plog"] if pdep else (line["A"], line["n"], line["Ea"])) is not None
                    and chemkin_lines.same_rate(rate, line["plog"] if pdep else (line["A"], line["n"], line["Ea"]),
                                                self.molecules)]
            # The entry's own line first, then lines of the entry's records in its direction.
            hits.sort(key=lambda line: (_names_key(line["reactants"], line["products"]) != own_names,
                                        self.direction(line["reactants"], line["products"]) != own_direction,
                                        self.identity(line["reactants"], line["products"]) != own_identity))
            line = hits[0] if hits else None
            if line is not None:
                self.used.add(id(line))
            if line is None or self.direction(line["reactants"], line["products"]) == own_direction:
                own.append(term)
            else:
                other.setdefault((tuple(line["reactants"]), tuple(line["products"]), line["reversible"]), []).append(term)
        if not other:
            return whole
        parts = [(entry.item, _combined(own, data), entry.short_desc)] if own else []
        for (reactants, products, reversible), terms in other.items():
            reaction = Reaction(reactants=[self.species[n] for n in reactants],
                                products=[self.species[n] for n in products], reversible=reversible)
            comment = ("The chemkin file reaction is " + " + ".join(reactants) + (" <=> " if reversible else " => ")
                       + " + ".join(products))
            parts.append((reaction, _combined(terms, data), comment))
            self.moved += len(terms)
        return parts

    def dropped_lines(self, entries):
        """[(RMG reaction, kinetics, comment)] for the irreversible CHEMKIN lines that no library
        entry holds, where an irreversible entry holds the reaction in the other direction or with
        another collider. RMG-Py's CHEMKIN reader reads each from the file. A line is held when a
        term came from it (parts, so call this after parts for every entry), when an entry has its
        direction and collider, or when an entry has its rate. A line RMG-Py cannot read goes to
        `unread`."""
        if not self.twins:
            return []
        held = defaultdict(list)
        for entry in entries:
            labels = ([s.label for s in entry.item.reactants], [s.label for s in entry.item.products])
            key = self.key(*labels)
            if key in self.twins:
                held[key].append((self.direction(*labels), _collider(entry.item, entry.data), entry))
        parts = []
        for key, lines in self.twins.items():
            entries_of_key = held.get(key, [])
            rates = [_rates(entry.data) for _, _, entry in entries_of_key]
            if (all(entry.item.reversible for _, _, entry in entries_of_key) or None in rates):
                continue
            rates = [rate for terms in rates for rate in terms]
            for line in lines:
                direction = self.direction(line["reactants"], line["products"])
                collider = (line["collider"] or "").upper() or None
                if (id(line) in self.used or (direction, collider) in {(d, c) for d, c, _ in entries_of_key}
                        or any(len(rate) == len(_line_rates(line)) and all(
                            chemkin_lines.same_rate(a, b, self.molecules) for a, b in zip(rate, _line_rates(line)))
                            for rate in rates)):
                    continue
                reaction = self.read_line(line)
                if reaction is not None:
                    parts.append((reaction, reaction.kinetics, f"The chemkin file reaction is {reaction}"))
        return parts

    def colliders(self):
        """upper-case name -> species for the names of the model's thermo library that the kinetics
        dictionary lacks: species the download has that only a collider efficiency names
        (Serinyel N2 and AR). Read once."""
        if self._colliders is None:
            self._colliders = {}
            thermo_path = os.path.join(self.model_dir, "RMG-Py-thermo-library", "ThermoLibrary.py")
            if os.path.exists(thermo_path):
                for label, entry in load_thermo_library(thermo_path, "colliders", self.states).entries.items():
                    if label.upper() not in self.spelling:
                        self._colliders[label.upper()] = Species(label=label, molecule=[entry.item])
        return self._colliders

    def read_line(self, line):
        """The line as RMG-Py's CHEMKIN reader reads it, with the library's species and, for collider
        efficiencies, the thermo library's; None (and the line in `unread`) when it cannot."""
        a_units, ea_units = self.units
        names = {**self.colliders(), **{upper: self.species[label] for upper, label in self.spelling.items()}}
        try:
            if ea_units is None:
                raise ValueError("an Ea unit RMG-Py cannot read")
            reaction = read_kinetics_entry(chemkin_lines.kinetics_entry(line, names), names, a_units, [], ea_units)
            if reaction.reversible != line["reversible"]:
                raise ValueError("another arrow than the line's")
        except Exception as error:
            self.unread.append((line["line"], f"{type(error).__name__}: {error}"))
            logger.warning(f"CHEMKIN line {line['line']} not read ({error}): {line['text']}")
            return None
        return reaction


def import_kinetics(kinetics_path, kinetic_model, models, only_types=None, states=None,
                    repeats=None):
    """Import a model's kinetics library; only_types limits it to RMG kinetics class names.

    `states` (label -> electronic state) defaults to the model's SMILES.txt; a term symbol in
    the library dictionary wins over it. `repeats` (later label -> first label) defaults to
    model_repeats; a rate that writes a later label names it. A merged entry's terms go to the
    reactions their CHEMKIN lines write (MergedRates), and a full import (no only_types) adds the
    irreversible lines RMG-models left out of a reaction the model writes in both directions or
    for two colliders (MergedRates.dropped_lines). Returns
    counts of imported, skipped and failed entries, of moved terms and of added lines."""
    local_context = kinetics_local_context()
    repeats = model_repeats(kinetics_path, kinetic_model, states) if repeats is None else repeats
    # Older RMG accepted reactions that RMG 4 refuses; skip just those, not the whole library.
    library = TolerantKineticsLibrary(label=kinetic_model.model_name)
    library.SKIP_DUPLICATES = True
    # The states and later names keep reactions of an excited state apart from the ground
    # state's, and furop2's apart from furop1's, on loading.
    library.declared_states = model_states(kinetics_path) if states is None else states
    library.declared_variants = {later: later for later in repeats}
    library.load(kinetics_path, local_context=local_context)
    states = {**library.declared_states, **getattr(library, "term_symbols", {})}
    labels = labels_by_structure_key(getattr(library, "species_dict", None), states, repeats)
    # Species looked up during this import. Each entry's new lookups are kept apart until the
    # entry commits, because a failed entry rolls back the species it created.
    cache = {}
    counts = {"imported": 0, "skipped": 0, "failed": 0, "rejected": len(library.rejected)}
    for label, reason in library.rejected:
        logger.warning(f"RMG cannot load reaction {label} ({reason}); skipped")
    merged = MergedRates(kinetics_path, library, states, repeats)
    for entry in library.entries.values():
        if only_types is not None and entry.data.__class__.__name__ not in only_types:
            counts["skipped"] += 1
            continue
        pending = {}
        lookups = ChainMap(pending, cache)
        try:
            with transaction.atomic():
                for rmg_reaction, rmg_kinetics_data, comment in merged.parts(entry):
                    import_kinetics_link(kinetic_model, rmg_reaction, rmg_kinetics_data, comment, models,
                                         states, lookups, repeats, labels)
            cache.update(pending)
            counts["imported"] += 1
        except Exception:
            counts["failed"] += 1
            logger.exception(f"Failed to import reaction {entry.label}")
    if only_types is None:
        for rmg_reaction, rmg_kinetics_data, comment in merged.dropped_lines(library.entries.values()):
            pending = {}
            lookups = ChainMap(pending, cache)
            try:
                with transaction.atomic():
                    import_kinetics_link(kinetic_model, rmg_reaction, rmg_kinetics_data, comment, models,
                                         states, lookups, repeats, labels)
                cache.update(pending)
                counts["added_lines"] = counts.get("added_lines", 0) + 1
            except Exception:
                counts["failed"] += 1
                logger.exception(f"Failed to import CHEMKIN reaction {rmg_reaction}")
        counts["failed"] += len(merged.unread)
    if merged.moved:
        counts["moved_terms"] = merged.moved
    return counts


def kinetics_names_model(models):
    """The KineticsCommentName model of these models, or None for historical models without it."""
    return next((rel.related_model for rel in models.KineticsComment._meta.related_objects
                 if rel.get_accessor_name() == "names"), None)


def later_names(kinetic_model, rmg_reaction, models, states, lookups, repeats):
    """[(reactant, SpeciesName id)] for each time the reaction writes one of the model's later
    labels (see model_repeats), sorted: what tells this rate apart from the rate of the first
    label's reaction, which has the same species records."""
    names = []
    for reactant, side in ((True, rmg_reaction.reactants), (False, rmg_reaction.products)):
        for rmg_species in side:
            label = rmg_species.label
            if label not in (repeats or {}):
                continue
            key = ("name", label, (states or {}).get(label, ""))
            if key not in lookups:
                species = labelled_species(kinetic_model, rmg_species, models, states, lookups)
                lookups[key] = models.SpeciesName.objects.filter(
                    species=species, kinetic_model=kinetic_model, name=label).order_by("pk").values_list(
                    "pk", flat=True).first()
            names.append((reactant, lookups[key]))
    return sorted(names)


def import_kinetics_link(kinetic_model, rmg_reaction, rmg_kinetics_data, comment, models, states, lookups,
                         repeats, labels):
    """The reaction, kinetics row and model link of one library rate; see import_kinetics."""
    reaction = get_or_create_reaction(
        kinetic_model, rmg_reaction, models, states, cache=lookups)
    kinetics_data = create_kinetics_data(kinetic_model, rmg_kinetics_data, models)
    base_fields = get_base_kinetics_data_fields(rmg_kinetics_data)
    identity = {"reaction": reaction, "raw_data": kinetics_data}
    if has_field(models.Kinetics, "specific_collider"):
        # H + O2 (+AR) <=> HO2 (+AR): the library names the collider only in the
        # label, and RMG keeps it on the reaction, not in the efficiencies.
        collider = getattr(rmg_reaction, "specific_collider", None)
        identity["specific_collider"] = (
            labelled_species(kinetic_model, collider, models, states, lookups)
            if collider is not None else None)
    efficiencies = collider_efficiencies(
        kinetic_model, rmg_kinetics_data, models, labels=labels, cache=lookups)
    if has_field(models.Kinetics, "efficiencies_hash"):
        # Another model's record with the same parameters but other efficiencies
        # (H2O 7.5 where this library has 0.0) is not this model's rate.
        identity["efficiencies_hash"] = kd.efficiencies_hash(
            (species.pk, efficiency) for species, efficiency in efficiencies)

    kinetics_instance, created = models.Kinetics.objects.get_or_create(
        **identity, defaults=base_fields
    )
    if created:
        for species, efficiency in efficiencies:
            models.Efficiency.objects.create(
                species=species, kinetics=kinetics_instance, efficiency=efficiency)
        index_new_rows(models, kinetics=kinetics_instance)

    link_fields = {"comment": comment}
    if has_field(models.KineticsComment, "reversible"):
        # The model's own arrow: the reaction record keeps the first import's.
        link_fields["reversible"] = rmg_reaction.reversible
    # One link per model, kinetics row and later names: furop1 + H and furop2 + H with one rate
    # are one kinetics row of one reaction record, and two of the model's lines.
    names_model = kinetics_names_model(models)
    names = later_names(kinetic_model, rmg_reaction, models, states, lookups, repeats) if names_model else []
    links = models.KineticsComment.objects.filter(kinetics=kinetics_instance, kinetic_model=kinetic_model)
    if names_model:
        written = defaultdict(list)
        for link_id, reactant, name_id in names_model.objects.filter(kinetics_comment__in=links).values_list(
                "kinetics_comment_id", "reactant", "species_name_id"):
            written[link_id].append((reactant, name_id))
        link = next((l for l in links.order_by("pk") if sorted(written[l.pk]) == names), None)
    else:
        link = links.order_by("pk").first()
    if link is None:
        link = models.KineticsComment.objects.create(
            kinetics=kinetics_instance, kinetic_model=kinetic_model, **link_fields)
        if names:
            names_model.objects.bulk_create([
                names_model(kinetics_comment=link, species_name_id=name_id, reactant=reactant)
                for reactant, name_id in names])
    elif link_fields.get("reversible", link.reversible) != link.reversible:
        link.reversible = link_fields["reversible"]
        link.save(update_fields=["reversible"])


def import_thermo(thermo_path, kinetic_model, models, states=None):
    """Import a model's thermo library.

    `states` (label -> electronic state) defaults to the model's SMILES.txt; an entry's term
    symbol wins over it. Returns counts of imported and failed entries, `excited_states`
    (label -> state), `repeats` (label -> the earlier label of its structure and state: both are
    names of one record, each with its own thermo link, see model_repeats) and
    `skipped_duplicates`: the entries left out because an earlier entry has the same label or
    the adjacency list is not readable (see TolerantThermoLibrary).
    """
    library = load_thermo_library(thermo_path, kinetic_model.model_name, states)
    _thermo_repeats[_repeats_key(thermo_path, states)] = dict(library.repeats)
    counts = {"imported": 0, "failed": 0, "skipped_duplicates": list(library.skipped),
              "excited_states": {label: state for label, state in library.states.items() if state},
              "repeats": dict(library.repeats)}
    for skipped in library.skipped:
        logger.warning(f"Thermo entry {skipped['label']} skipped: {skipped['reason']}")
    named = set(library.repeats) | set(library.repeats.values())
    for species_name, entry in library.entries.items():
        logger.info(f"Importing Thermo entry for {species_name}")
        try:
            with transaction.atomic():
                import_thermo_entry(kinetic_model, species_name, entry, models,
                                    library.states.get(species_name, ""), species_name in named)
            counts["imported"] += 1
        except Exception:
            counts["failed"] += 1
            logger.exception(f"Failed to import thermo entry {species_name}")
    return counts


def model_thermo(species, fields, models):
    """The species' thermo row with these coefficients, created when there is none.

    Thermo enrichment keeps its own copy of a polynomial for every source that lists it
    (ThermoRecord.nasa_thermo, often identical to a model's), so several rows can match; the
    copies a provider record owns are not a model's row and are left out.
    """
    rows = models.Thermo.objects.filter(species=species, **fields)
    if has_field(models.Thermo, "provider_record"):
        rows = rows.filter(provider_record__isnull=True)
    thermo = rows.order_by("pk").first()
    if thermo is None:
        thermo = models.Thermo.objects.create(species=species, **fields)
    return thermo


def import_thermo_entry(kinetic_model, species_name, entry, models, electronic_state="", named=False):
    """`named`: the model has another name for this structure and state (model_repeats), so the
    thermo link says which name it is for."""
    species = get_or_create_species(
        kinetic_model, species_name, [entry.item], models, electronic_state=electronic_state)
    thermo_data = entry.data
    poly1, poly2 = thermo_data.polynomials

    # Sanitise temperature ranges: some RMG entries have 0 K break
    # temperatures or poly2.Tmin < poly1.Tmax (overlapping ranges).
    t_min_1 = poly1.Tmin.value_si
    t_max_1 = poly1.Tmax.value_si
    t_min_2 = poly2.Tmin.value_si
    t_max_2 = poly2.Tmax.value_si

    if t_max_1 == 0:
        t_max_1 = 1000.0
    if t_min_2 == 0:
        t_min_2 = 1000.0
    if t_min_2 < t_max_1:
        t_min_2 = t_max_1

    thermo = model_thermo(species, {
        "coeffs_poly1": poly1.coeffs.tolist(),
        "coeffs_poly2": poly2.coeffs.tolist(),
        "temp_min_1": t_min_1,
        "temp_max_1": t_max_1,
        "temp_min_2": t_min_2,
        "temp_max_2": t_max_2,
    }, models)
    # One link per model, thermo row and name, so importing a model again adds no second link.
    # Two names with the same polynomials share the row and have a link each.
    comment = entry.long_desc or entry.short_desc or ""
    name_field = {}
    if named and has_field(models.ThermoComment, "species_name"):
        name_field["species_name"] = models.SpeciesName.objects.filter(
            species=species, kinetic_model=kinetic_model, name=species_name).order_by("pk").first()
    thermo_comment = models.ThermoComment.objects.filter(
        kinetic_model=kinetic_model, thermo=thermo, **name_field).first()
    if thermo_comment is None:
        models.ThermoComment.objects.create(
            kinetic_model=kinetic_model, thermo=thermo, comment=comment, **name_field)
    elif comment and not thermo_comment.comment:
        thermo_comment.comment = comment
        thermo_comment.save(update_fields=["comment"])


def create_and_save_authorships(source, author_data, models):
    for order, author_datum in enumerate(author_data):
        firstname = author_datum.get("given")
        lastname = author_datum.get("family")
        author_fields = filter_fields({"firstname": firstname, "lastname": lastname})
        author, _ = models.Author.objects.get_or_create(**author_fields)
        authorship, _ = models.Authorship.objects.get_or_create(
            source=source, author=author, defaults={"order": order}
        )
        safe_save(author)
        safe_save(authorship)


def import_source(source_path, kinetic_model, models):
    crossref = habanero.Crossref(mailto="kianmehrabani@gmail.com")
    try:
        doi = get_doi(source_path)
        reference = crossref.works(ids=doi).get("message", "") if doi else {}
        created_info = reference.get("created", "")
        date = parser.parse(created_info.get("date-time", "")) if created_info else None
        year = date.year if date else ""
        title_body = reference.get("title", "")
        source_title = title_body[0] if isinstance(title_body, list) else title_body
        name_body = reference.get("short-container-title", "")
        journal_name = name_body[0] if isinstance(name_body, list) else name_body
        volume_number = reference.get("volume", "")
        page_numbers = reference.get("page", "")
        author_data = reference.get("author")
        fields = dict(
            publication_year=year,
            source_title=source_title,
            journal_name=journal_name,
            journal_volume_number=volume_number,
            page_numbers=page_numbers,
        )
        source, created = models.Source.objects.get_or_create(doi=doi)
        if created:
            for k, v in fields.items():
                setattr(source, k, v)

        source.kineticmodel_set.add(kinetic_model)
        source.save()
        # Only populate authorships for a freshly created source; an existing
        # source already has them, and re-adding would duplicate Authorship rows.
        if created and author_data is not None:
            create_and_save_authorships(source, author_data, models)
        elif author_data is None:
            logger.warning("Could not find author data")
    except FileNotFoundError:
        logger.warning("source.txt not found")


def get_doi(source_path):
    """
    Get the DOI from the source.txt file
    """

    with open(source_path, "r") as f:
        source = f.read()

    regex = re.compile(r"10.\d{4,9}/\S+")
    matched_list = regex.findall(source)
    matched_list = [d.rstrip(".") for d in matched_list]
    # There are sometimes other trailing characters caught up, like ) or ]
    # We should probably clean up the source.txt files
    # But let's try cleaning them here.

    def clean(doi):
        for opening, closing in ["()", "[]"]:
            if doi.endswith(closing):
                if doi.count(closing) - doi.count(opening) == 1:
                    # 1 more closing than opening
                    # remove the last closing
                    doi = doi[:-1]
        return doi

    matched_list = [clean(d) for d in matched_list]
    matched_set = set(matched_list)

    if len(matched_set) == 0:
        raise ValueError("DOI not found")
    elif len(matched_set) > 1:
        raise ValueError("Found multiple DOIS")
    else:
        return matched_list[0]


# def get_models(path, ignore_list=[]):
#     """
#     Walk the given `path` looking for libraries and source files.
#     Skips any paths that end with something in the skip_list
#     (eg. skip_list=['PCI2011/193-Mehl'])
#     Returns tuples of the following form:
#         model_name, thermo_library, kinetics_library, source_file
#     """

#     ignore_list.extend([".git", "translations", "modelComparer"])
#     root, dirs, _ = next(os.walk(path))
#     for dir in dirs:
#         pdir = Path(dir)
#         if pdir.name not in ignore_list:
#             rmg_model_name = pdir.name
#             thermo_path = root / pdir / "RMG-Py-thermo-library" / "ThermoLibrary.py"
#             kinetics_path = root / pdir / "RMG-Py-kinetics-library" / "reactions.py"
#             source_path = root / pdir / "source.txt"
#             yield rmg_model_name, str(thermo_path), str(kinetics_path), str(source_path)


def get_models(path, ignore_list=[]):
    """
    Walk the given `path` looking for libraries and source files.
    Skips any paths that end with something in the skip_list
    (eg. skip_list=['PCI2011/193-Mehl'])
    
    Handles both:
    - Direct models: folder/RMG-Py-thermo-library/ThermoLibrary.py
    - Nested models: folder/subfolder/RMG-Py-thermo-library/ThermoLibrary.py
    
    For nested models, the model_name is "parent/subfolder" (e.g., "CombFlame2013/17-Malewicki")
    
    Returns tuples of the following form:
        model_name, thermo_library, kinetics_library, source_file
    """
    
    ignore_list = ignore_list.copy()  # Don't modify the default parameter
    ignore_list.extend([".git", "translations", "modelComparer"])
    
    # Convert to Path object for better handling
    base_path = Path(path)
    
    # Check if path exists
    if not base_path.exists():
        logger.error(f"Path does not exist: {path}")
        return
    
    def check_model_dir(model_dir, model_name):
        """Check if a directory contains RMG libraries and return model info if valid."""
        thermo_path = model_dir / "RMG-Py-thermo-library" / "ThermoLibrary.py"
        kinetics_path = model_dir / "RMG-Py-kinetics-library" / "reactions.py"
        source_path = model_dir / "source.txt"
        
        # Check if this directory has the libraries
        if thermo_path.exists() or kinetics_path.exists():
            return (
                model_name,
                str(thermo_path) if thermo_path.exists() else None,
                str(kinetics_path) if kinetics_path.exists() else None,
                str(source_path) if source_path.exists() else None,
            )
        return None
    
    # Walk through directories
    try:
        for item in sorted(base_path.iterdir()):
            if not item.is_dir():
                continue
                
            if item.name in ignore_list:
                continue
            
            top_level_name = item.name
            
            # Check if this is in the ignore list (with path prefix)
            if any(skip in top_level_name for skip in ignore_list):
                continue
            
            # First, check if this directory itself is a model (has libraries directly)
            result = check_model_dir(item, top_level_name)
            if result:
                yield result
            else:
                # No direct libraries - check subdirectories for nested models
                for sub_dir in sorted(item.iterdir()):
                    if not sub_dir.is_dir():
                        continue
                    if sub_dir.name.startswith('.') or sub_dir.name in ignore_list:
                        continue
                    
                    # Create nested model name
                    nested_name = f"{top_level_name}/{sub_dir.name}"
                    
                    # Check if nested name is in ignore list
                    if any(skip in nested_name for skip in ignore_list):
                        logger.info(f"Skipping {nested_name} (in ignore list)")
                        continue
                    
                    result = check_model_dir(sub_dir, nested_name)
                    if result:
                        yield result
                        
    except Exception as e:
        logger.error(f"Error walking directory {path}: {e}")