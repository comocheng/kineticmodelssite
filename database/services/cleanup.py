"""Repair the identity defects that older imports left in the database.

Before Oct 2026 the importer identified a species by the exact set of its resonance forms, so
one species often became two records (a thermo library gives one form, a reaction gives all of
them), and it put excited states (OH*) on the ground-state record. Importing again with the
current importer adds correct links but deletes nothing, so the old links stay next to the new
ones. Four steps repair this. Each step runs in transactions and writes only with apply=True;
without it the work is done and rolled back, so a dry run reports exactly what would change.

1. merge_split_species: one record per species (records in one electronic state that share
   a structure key).
   Every row that refers to another record of the same species is moved to the kept record,
   and reactions and kinetics that become identical are merged as well.
2. rebuild_model_links: replaces a model's names, thermo links and kinetics links with what the
   current importer makes from the model's library. An old link stays when the library entry
   that would replace it could not be imported, so an import failure loses nothing.
3. prune_unlinked_rows: deletes thermo, kinetics, reaction and species rows that nothing refers
   to any more. Rows that only provider data or derived tables refer to are kept and counted.
4. integrity_report: counts each defect. Run it before and after the steps as the evidence.
"""
import itertools
import re
from collections import Counter, defaultdict
from types import SimpleNamespace

from django.db import IntegrityError, transaction
from django.db.models import Count

from database import models as db
from database.models.kinetic_data import efficiencies_hash
from database.scripts.import_rmg_models import (
    get_reaction_hash, get_species_hash, import_kinetics, import_thermo)

MODELS = SimpleNamespace(**{name: getattr(db, name) for name in (
    "KineticModel", "Source", "Author", "Authorship", "Thermo", "ThermoComment", "Species", "Formula",
    "Isomer", "Structure", "SpeciesName", "Efficiency", "Kinetics", "KineticsComment", "Reaction",
    "Stoichiometry")})

# Rows that belong to the row they refer to and go with it: they do not keep it in use.
OWNED_ROWS = {db.Kinetics: (db.Efficiency,), db.Reaction: (db.Stoichiometry,)}
EXCITED_NAME = re.compile(r"(\*|EX)$", re.I)


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def references(model):
    """(table, field) for every foreign key to `model`, including the rows of an automatic
    many-to-many table such as ChemistryBlock.reactions. Found from the models, so a table
    added later is covered without a change here."""
    refs = []
    for rel in model._meta.related_objects:
        if rel.many_to_many:
            if rel.through._meta.auto_created:
                field = next(f.name for f in rel.through._meta.get_fields()
                             if f.many_to_one and f.related_model is model)
                refs.append((rel.through, field))
            # A many-to-many relation with its own table (SpeciesName, Stoichiometry, ...) is
            # also listed as that table's foreign key.
            continue
        refs.append((rel.related_model, rel.field.name))
    return refs


def referenced_ids(model, skip=()):
    """Primary keys of `model` rows that some other row refers to, by referring table."""
    used = {}
    for table, field in references(model):
        if table in skip:
            continue
        ids = set(table.objects.exclude(**{f"{field}__isnull": True})
                  .values_list(field, flat=True).distinct())
        if ids:
            used[table._meta.label] = ids
    return used


def move_references(model, drop_ids, keep_id, skip=()):
    """Point every row that refers to one of `drop_ids` at `keep_id`. Returns rows moved per
    table. A unique rule broken by the move stops the step with the table's name."""
    moved = Counter()
    for table, field in references(model):
        if table in skip:
            continue
        rows = table.objects.filter(**{f"{field}__in": drop_ids})
        if table._meta.auto_created:
            # A many-to-many row the kept row already has would be a second copy.
            other = next(f.name for f in table._meta.get_fields() if f.many_to_one and f.name != field)
            have = set(table.objects.filter(**{field: keep_id}).values_list(other, flat=True))
            for row in rows.order_by("pk"):
                target = getattr(row, f"{other}_id")
                if target in have:
                    row.delete()
                else:
                    table.objects.filter(pk=row.pk).update(**{field: keep_id})
                    have.add(target)
                    moved[table._meta.label] += 1
            continue
        try:
            with transaction.atomic():
                count = rows.update(**{field: keep_id})
        except IntegrityError as error:
            raise IntegrityError(f"moving {table._meta.label}.{field} to {keep_id}: {error}") from error
        if count:
            moved[table._meta.label] += count
    return moved


def keep_oldest(model, group_fields, **filters):
    """Delete all but the oldest row of each group of rows with the same values."""
    seen, extra = set(), []
    for row in model.objects.filter(**filters).order_by("pk").values("pk", *group_fields):
        key = tuple(row[f] for f in group_fields)
        if key in seen:
            extra.append(row["pk"])
        else:
            seen.add(key)
    if extra:
        model.objects.filter(pk__in=extra).delete()
    return len(extra)


# ---------------------------------------------------------------------------
# Species identity
# ---------------------------------------------------------------------------

def species_identities():
    """species id -> (structure keys of its isomers, electronic state).

    Records without structure keys are left out."""
    keys_of_isomer = defaultdict(set)
    for isomer_id, key in db.Structure.objects.exclude(structure_key="").values_list("isomer_id", "structure_key"):
        keys_of_isomer[isomer_id].add(key)
    keys = defaultdict(set)
    for species_id, isomer_id in db.Species.isomers.through.objects.values_list("species_id", "isomer_id"):
        keys[species_id] |= keys_of_isomer[isomer_id]
    states = dict(db.Species.objects.values_list("pk", "electronic_state"))
    return {sp: (frozenset(k), states[sp]) for sp, k in keys.items() if k}


def split_groups():
    """Groups of records that are one species, the record to keep first.

    Records in one electronic state that share a structure key are one species (spin states
    have different keys). Resonance forms usually share one key, but not when their InChI H
    layers differ: an older import left CH2COOH as a record with [CH2]C(=O)O and another with
    that form and C=C([O])O. So records are joined through any key they share, also through a
    third record, not only when all their keys are the same. The kept record is the one the
    importer picks: the most resonance forms, then the oldest."""
    parent = {}

    def root(species_id):
        while parent[species_id] != species_id:
            parent[species_id] = parent[parent[species_id]]
            species_id = parent[species_id]
        return species_id

    first_holder = {}
    for species_id, (keys, state) in species_identities().items():
        parent.setdefault(species_id, species_id)
        for key in keys:
            holder = first_holder.setdefault((key, state), species_id)
            parent[root(species_id)] = root(holder)
    groups = defaultdict(list)
    for species_id in parent:
        groups[root(species_id)].append(species_id)
    size = dict(db.Species.objects.annotate(n=Count("isomers")).values_list("pk", "n"))
    return sorted(sorted(ids, key=lambda sp: (-size[sp], sp))
                  for ids in groups.values() if len(ids) > 1)


def stoichiometry_hash(reaction_id):
    rows = db.Stoichiometry.objects.filter(reaction_id=reaction_id).values_list("coeff", "species_id")
    return get_reaction_hash([(coeff, SimpleNamespace(id=species)) for coeff, species in rows])


def rewrite_stoichiometry(reaction_ids, new_species):
    """Replace species in these reactions (old id -> new id), adding up a species that then
    appears twice on one side."""
    for reaction_id in reaction_ids:
        rows = list(db.Stoichiometry.objects.filter(reaction_id=reaction_id))
        total = Counter()
        for row in rows:
            species = new_species.get(row.species_id, row.species_id)
            total[(species, row.coeff > 0)] += row.coeff
        if sorted((r.species_id, r.coeff) for r in rows) == sorted((s, c) for (s, _), c in total.items()):
            continue
        db.Stoichiometry.objects.filter(reaction_id=reaction_id).delete()
        db.Stoichiometry.objects.bulk_create([
            db.Stoichiometry(reaction_id=reaction_id, species_id=species, coeff=coeff)
            for (species, _), coeff in total.items()])


def merge_species_group(ids):
    """Merge the records `ids[1:]` into `ids[0]`. Returns the ids of reactions that changed."""
    keep_id, drop_ids = ids[0], ids[1:]
    reactions = set(db.Stoichiometry.objects.filter(species__in=drop_ids).values_list("reaction_id", flat=True))
    rewrite_stoichiometry(reactions, {drop: keep_id for drop in drop_ids})
    move_references(db.Species, drop_ids, keep_id, skip=(db.Stoichiometry,))
    isomers = list(db.Isomer.objects.filter(species__in=drop_ids).distinct())
    keep = db.Species.objects.get(pk=keep_id)
    for field in ("prime_id", "cas_number"):
        if not getattr(keep, field):
            value = next((v for v in db.Species.objects.filter(pk__in=drop_ids)
                          .values_list(field, flat=True) if v), "")
            setattr(keep, field, value)
    keep.save(update_fields=["prime_id", "cas_number"])
    db.Species.objects.filter(pk__in=drop_ids).delete()
    keep.isomers.add(*isomers)
    keep.hash = get_species_hash(keep.isomers.all(), keep.electronic_state)
    keep.save(update_fields=["hash"])
    # Names: one row per model and name, and no empty placeholder next to a name.
    keep_oldest(db.SpeciesName, ("kinetic_model", "name"), species_id=keep_id)
    named = set(db.SpeciesName.objects.filter(species_id=keep_id).exclude(name="")
                .values_list("kinetic_model", flat=True))
    db.SpeciesName.objects.filter(species_id=keep_id, name="", kinetic_model__in=named).delete()
    keep_oldest(db.Efficiency, ("kinetics", "species"), species_id=keep_id)
    return reactions


def merge_kinetics(keep_id, drop_id):
    """Merge a kinetics row into the identical one of the same reaction."""
    move_references(db.Kinetics, [drop_id], keep_id)
    keep_oldest(db.KineticsComment, ("kinetic_model",), kinetics_id=keep_id)
    keep_oldest(db.Efficiency, ("species",), kinetics_id=keep_id)
    db.Kinetics.objects.filter(pk=drop_id).delete()


def refresh_efficiencies_hashes(kinetics_ids, report):
    """Give these kinetics rows the fingerprint of their efficiencies after a species merge
    moved them; merge a row into the identical one of the same reaction."""
    for kinetics in db.Kinetics.objects.filter(pk__in=kinetics_ids).order_by("pk"):
        new_hash = efficiencies_hash(kinetics.efficiency_set.values_list("species_id", "efficiency"))
        if new_hash == kinetics.efficiencies_hash:
            continue
        twin = db.Kinetics.objects.filter(
            reaction_id=kinetics.reaction_id, raw_data=kinetics.raw_data,
            specific_collider_id=kinetics.specific_collider_id, efficiencies_hash=new_hash,
        ).exclude(pk=kinetics.pk).values_list("pk", flat=True).first()
        if twin is not None:
            merge_kinetics(twin, kinetics.pk)
            report["kinetics_merged"] += 1
        else:
            db.Kinetics.objects.filter(pk=kinetics.pk).update(efficiencies_hash=new_hash)
        report["kinetics_with_changed_efficiencies"] += 1


def merge_reaction_pair(keep_id, drop_id, report):
    """Merge a reaction into the one with the same species and coefficients."""
    for kinetics in db.Kinetics.objects.filter(reaction_id=drop_id):
        twin = db.Kinetics.objects.filter(
            reaction_id=keep_id, raw_data=kinetics.raw_data,
            specific_collider_id=kinetics.specific_collider_id,
            efficiencies_hash=kinetics.efficiencies_hash).first()
        if twin:
            merge_kinetics(twin.pk, kinetics.pk)
            report["kinetics_merged"] += 1
        else:
            db.Kinetics.objects.filter(pk=kinetics.pk).update(reaction_id=keep_id)
    move_references(db.Reaction, [drop_id], keep_id, skip=(db.Kinetics, db.Stoichiometry))
    # Counted only: each model's kinetics link keeps its own arrow, which the exports use.
    reversible = set(db.Reaction.objects.filter(pk__in=[keep_id, drop_id]).values_list("reversible", flat=True))
    if len(reversible) > 1:
        report["merged_reactions_with_different_reversible_flag"] += 1
    db.Reaction.objects.filter(pk=drop_id).delete()


def merge_reactions(reaction_ids, report):
    """Give these reactions the hash of their new stoichiometry; merge a reaction into an
    existing one with the same stoichiometry."""
    from database.services import chemistry_index
    for reaction_id in sorted(reaction_ids):
        if not db.Reaction.objects.filter(pk=reaction_id).exists():
            continue
        new_hash = stoichiometry_hash(reaction_id)
        twin = db.Reaction.objects.filter(hash=new_hash).exclude(pk=reaction_id).values_list("pk", flat=True).first()
        keep_id = reaction_id
        if twin is not None:
            keep_id, drop_id = sorted([reaction_id, twin])
            merge_reaction_pair(keep_id, drop_id, report)
            report["reactions_merged"] += 1
        db.Reaction.objects.filter(pk=keep_id).update(hash=new_hash)
        chemistry_index.index_reaction(db.Reaction.objects.get(pk=keep_id))


def merge_split_species(apply=False, log=print):
    """Step 1. Returns counts of what was (or, in a dry run, would be) merged."""
    report = Counter()
    with transaction.atomic():
        groups = split_groups()
        report["split_groups"] = len(groups)
        report["records_merged_away"] = sum(len(g) - 1 for g in groups)
        reactions = set()
        for n, ids in enumerate(groups, 1):
            reactions |= merge_species_group(ids)
            if n % 100 == 0:
                log(f"  merged {n} of {len(groups)} groups")
        report["reactions_with_changed_species"] = len(reactions)
        # A collider efficiency on a merged record changes the rate's fingerprint.
        refresh_efficiencies_hashes(set(db.Efficiency.objects.filter(
            species_id__in=[ids[0] for ids in groups]).values_list("kinetics_id", flat=True)), report)
        merge_reactions(reactions, report)
        if not apply:
            transaction.set_rollback(True)
    return dict(report)


# ---------------------------------------------------------------------------
# Model links
# ---------------------------------------------------------------------------

def model_links(model):
    return (
        list(db.SpeciesName.objects.filter(kinetic_model=model).values("species_id", "name")),
        list(db.ThermoComment.objects.filter(kinetic_model=model)
             .values("thermo_id", "thermo__species_id", "comment")),
        list(db.KineticsComment.objects.filter(kinetic_model=model)
             .values("kinetics_id", "kinetics__reaction_id", "kinetics__reaction__canonical_key", "comment",
                     "reversible")),
    )


def names_of_species(name_rows):
    """species id -> the model's names for it, from model_links()[0]."""
    names = defaultdict(set)
    for n in name_rows:
        if n["name"]:
            names[n["species_id"]].add(n["name"])
    return names


def label_equations(kinetics_rows, names, most=256):
    """kinetics id -> the reaction written with the model's species names, e.g. C3H5 + H = C3H6,
    as a set of spellings.

    It identifies a reaction across a corrected structure: the corrected species is a new
    record, so the reaction's species and canonical key change, but its names do not. A record
    an older import gave several names (C3H2, C3H2(S) and H2CCC(S) on one record) could stand
    for any of them, so the reaction gets one spelling per choice of names."""
    reactions = {k["kinetics__reaction_id"] for k in kinetics_rows}
    rows = defaultdict(list)
    for reaction_id, species_id, coeff in db.Stoichiometry.objects.filter(
            reaction_id__in=reactions).values_list("reaction_id", "species_id", "coeff"):
        labels = sorted(names.get(species_id, ())) or [f"#{species_id}"]
        rows[reaction_id].append([(label, coeff) for label in labels])
    spellings = {}
    for reaction_id, options in rows.items():
        count = 1
        for o in options:
            count *= len(o)
        spellings[reaction_id] = ({frozenset(choice) for choice in itertools.product(*options)} if count <= most
                                  else {frozenset(o[0] for o in options)})
    return {k["kinetics_id"]: spellings.get(k["kinetics__reaction_id"], set()) for k in kinetics_rows}


def run_import(func, path, model):
    """Import one library; returns (counts or error text, status): "ok" when every entry was
    imported, "absent" when the model has no such library, else "failed"."""
    if not path:
        return "no library", "absent"
    try:
        with transaction.atomic():
            counts = func(path, model, MODELS)
    except Exception as error:
        return f"library not loaded: {type(error).__name__}: {error}"[:300], "failed"
    counts = {k: v for k, v in counts.items() if k in ("imported", "failed", "rejected")}
    return counts, "failed" if counts.get("failed") or counts.get("rejected") else "ok"


def rebuild_model_links(model, thermo_path, kinetics_path):
    """Step 2 for one model. Replaces its names, thermo links and kinetics links with what the
    current importer makes from its libraries. An old link the importer did not make again is
    removed when the importer made a replacement (the same name, thermo for the same species,
    kinetics for the same reaction) or when every entry of the library was imported; otherwise
    it is kept, because the entry that would replace it failed. Thermo or kinetics links of a
    model without that library did not come from the library, so they are kept too. Returns the
    counts and examples.
    """
    old = model_links(model)
    for table in (db.SpeciesName, db.ThermoComment, db.KineticsComment):
        table.objects.filter(kinetic_model=model).delete()
    thermo_counts, thermo_status = run_import(import_thermo, thermo_path, model)
    kinetics_counts, kinetics_status = run_import(import_kinetics, kinetics_path, model)
    made = model_links(model)
    result = {"model": model.model_name, "thermo_import": thermo_counts, "kinetics_import": kinetics_counts}

    # Which old links the importer did not make again are kept. Names come from both
    # libraries; a library the model does not have names nothing.
    made_pairs = {(n["species_id"], n["name"]) for n in made[0]}
    made_names = {n["name"] for n in made[0] if n["name"]}
    named_species = {n["species_id"] for n in made[0]}
    names_ok = "failed" not in (thermo_status, kinetics_status)
    keep_names = {(n["species_id"], n["name"]) for n in old[0]
                  if (n["species_id"], n["name"]) not in made_pairs and not names_ok
                  and not (n["name"] in made_names if n["name"] else n["species_id"] in named_species)}
    # Thermo and kinetics made for the same species or reaction replace the old link. "The
    # same" is judged by record and, for a corrected structure (a new record), by the model's
    # names: the species' name, or the reaction written with names.
    old_names, made_names_of = names_of_species(old[0]), names_of_species(made[0])
    made_thermo = {t["thermo_id"] for t in made[1]}
    covered = {t["thermo__species_id"] for t in made[1]}
    covered_names = set().union(*(made_names_of[s] for s in covered)) if covered else set()
    keep_thermo = {t["thermo_id"]: t["comment"] for t in old[1]
                   if t["thermo_id"] not in made_thermo and thermo_status != "ok"
                   and t["thermo__species_id"] not in covered
                   and not old_names[t["thermo__species_id"]] & covered_names}
    made_kinetics = {k["kinetics_id"] for k in made[2]}
    made_reactions = {k["kinetics__reaction__canonical_key"] for k in made[2]} - {""}
    made_equations = set().union(*label_equations(made[2], made_names_of).values())
    old_equations = label_equations(old[2], old_names)
    keep_kinetics = {k["kinetics_id"]: k for k in old[2]
                     if k["kinetics_id"] not in made_kinetics and kinetics_status != "ok"
                     and k["kinetics__reaction__canonical_key"] not in made_reactions
                     and not old_equations[k["kinetics_id"]] & made_equations}
    db.SpeciesName.objects.bulk_create([
        db.SpeciesName(species_id=species, kinetic_model=model, name=name) for species, name in keep_names])
    db.ThermoComment.objects.bulk_create([
        db.ThermoComment(thermo_id=pk, kinetic_model=model, comment=c) for pk, c in keep_thermo.items()])
    # A kept link keeps its arrow too: its library entry failed, so nothing can set it again.
    db.KineticsComment.objects.bulk_create([
        db.KineticsComment(kinetics_id=pk, kinetic_model=model, comment=k["comment"][:1000],
                           reversible=k["reversible"])
        for pk, k in keep_kinetics.items()])

    # Counts compare the link rows before and after: a second copy of a link counts as removed.
    after = model_links(model)
    keys = (lambda n: (n["species_id"], n["name"]), lambda t: t["thermo_id"], lambda k: k["kinetics_id"])
    for label, key, before_rows, after_rows, kept in zip(
            ("names", "thermo_links", "kinetics_links"), keys, old, after, (keep_names, keep_thermo, keep_kinetics)):
        before_count, after_count = Counter(map(key, before_rows)), Counter(map(key, after_rows))
        result[label] = {"before": len(before_rows), "after": len(after_rows),
                         "removed": sum((before_count - after_count).values()),
                         "added": sum((after_count - before_count).values()),
                         "kept_after_import_failure": len(kept)}
    removed = Counter(map(keys[0], old[0])) - Counter(map(keys[0], after[0]))
    result["names_removed"] = sorted((name, species) for species, name in removed if name)[:50]
    return result


# ---------------------------------------------------------------------------
# Rows nothing refers to
# ---------------------------------------------------------------------------

def prune_unlinked_rows(apply=False):
    """Step 3. Deletes model thermo rows without a model link or provider record, kinetics
    without a model link, reactions without kinetics, and species nothing refers to. A row that
    only provider data or derived tables (ChemistryBlock, SemanticMapping, ...) refer to is
    kept and counted under that table."""
    report = {}
    with transaction.atomic():
        for model in (db.Thermo, db.Kinetics, db.Reaction, db.Species):
            used = referenced_ids(model, skip=OWNED_ROWS.get(model, ()))
            in_use = set().union(*used.values()) if used else set()
            unused = set(model.objects.values_list("pk", flat=True)) - in_use
            model.objects.filter(pk__in=unused).delete()
            report[model._meta.label] = {"deleted": len(unused)}
            # Kept only because of a table other than the model links: worth knowing.
            link_tables = {"database.ThermoComment", "database.KineticsComment", "database.Kinetics",
                           "database.SpeciesName", "database.Stoichiometry", "database.Efficiency",
                           "database.Thermo"}
            linked = set().union(*(ids for label, ids in used.items() if label in link_tables)) if used else set()
            report[model._meta.label]["kept_only_for"] = {
                label: len(ids - linked) for label, ids in used.items()
                if label not in link_tables and ids - linked}
        if not apply:
            transaction.set_rollback(True)
    return report


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def duplicate_rows(model, fields, **filters):
    counts = Counter(model.objects.filter(**filters).values_list(*fields))
    return sum(n - 1 for n in counts.values() if n > 1)


def integrity_report():
    """Counts of every defect the steps repair, plus examples. Reads only."""
    r = {}
    groups = split_groups()
    model_named = set(db.SpeciesName.objects.exclude(kinetic_model=None).values_list("species_id", flat=True))
    r["species_records"] = db.Species.objects.count()
    r["split_species"] = len(groups)
    r["split_species_records"] = sum(len(g) for g in groups)
    r["split_species_with_model_names_on_2plus_records"] = sum(
        1 for g in groups if len(model_named & set(g)) > 1)

    names = list(db.SpeciesName.objects.exclude(kinetic_model=None).values_list("kinetic_model", "species_id", "name"))
    records_of = defaultdict(set)
    for model, species, name in names:
        if name:
            records_of[(model, name)].add(species)
    r["model_names_on_2plus_records"] = sum(1 for v in records_of.values() if len(v) > 1)
    named_pairs = {(m, s) for m, s, n in names if n}
    r["name_links_empty"] = sum(1 for m, s, n in names if not n)
    r["name_links_empty_next_to_a_name"] = sum(1 for m, s, n in names if not n and (m, s) in named_pairs)
    r["name_links_duplicate"] = sum(c - 1 for c in Counter(names).values() if c > 1)

    r["thermo_links_duplicate"] = duplicate_rows(db.ThermoComment, ("kinetic_model", "thermo"))
    r["kinetics_links_duplicate"] = duplicate_rows(db.KineticsComment, ("kinetic_model", "kinetics"))
    r["thermo_links_to_provider_rows"] = db.ThermoComment.objects.filter(thermo__provider_record__isnull=False).count()

    isomers = defaultdict(list)
    for species_id, isomer_id in db.Species.isomers.through.objects.values_list("species_id", "isomer_id"):
        isomers[species_id].append(SimpleNamespace(id=isomer_id))
    r["species_with_stale_hash"] = sum(
        1 for pk, stored, state in db.Species.objects.values_list("pk", "hash", "electronic_state")
        if stored != get_species_hash(isomers[pk], state))
    stoich = defaultdict(list)
    for reaction_id, coeff, species_id in db.Stoichiometry.objects.values_list("reaction_id", "coeff", "species_id"):
        stoich[reaction_id].append((coeff, SimpleNamespace(id=species_id)))
    computed = {pk: get_reaction_hash(stoich[pk]) for pk in db.Reaction.objects.values_list("pk", flat=True)}
    stored = dict(db.Reaction.objects.values_list("pk", "hash"))
    r["reactions_with_stale_hash"] = sum(1 for pk in computed if computed[pk] != stored[pk])
    r["reactions_sharing_stoichiometry"] = sum(c - 1 for c in Counter(computed.values()).values() if c > 1)
    efficiencies = defaultdict(list)
    for kinetics_id, species_id, value in db.Efficiency.objects.values_list("kinetics_id", "species_id", "efficiency"):
        efficiencies[kinetics_id].append((species_id, value))
    r["kinetics_with_stale_efficiencies_hash"] = sum(
        1 for pk, stored in db.Kinetics.objects.values_list("pk", "efficiencies_hash")
        if stored != efficiencies_hash(efficiencies[pk]))

    for model in (db.Thermo, db.Kinetics, db.Reaction, db.Species):
        used = referenced_ids(model, skip=OWNED_ROWS.get(model, ()))
        in_use = set().union(*used.values()) if used else set()
        r[f"unreferenced_{model._meta.model_name}_rows"] = model.objects.exclude(pk__in=in_use).count()
    r["model_thermo_rows_without_model_link"] = db.Thermo.objects.filter(
        thermocomment__isnull=True, provider_record__isnull=True).count()
    r["kinetics_without_model_link"] = db.Kinetics.objects.filter(kineticscomment__isnull=True).count()

    ground = set(db.Species.objects.filter(electronic_state="").values_list("pk", flat=True))
    r["excited_names_on_ground_state_records"] = sum(
        1 for m, s, n in names if n and EXCITED_NAME.search(n) and s in ground)
    r["examples"] = {
        "split_species": [g[:4] for g in groups[:5]],
        "model_names_on_2plus_records": [
            (db.KineticModel.objects.get(pk=m).model_name, n, sorted(v))
            for (m, n), v in list((k, v) for k, v in records_of.items() if len(v) > 1)[:5]],
    }
    return r
