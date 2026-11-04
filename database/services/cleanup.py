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
   that would replace it could not be imported, so an import failure loses nothing, unless the
   old link's reaction is no longer the equation its comment names. prune_mismatched_links
   removes such links that an earlier rebuild kept.
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
    have different keys; a model's two names for one structure, furop1 and furop2, are two names
    of one record). Resonance forms usually share one key, but not when their InChI H
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
    keep_oldest_names(keep_id)
    named = set(db.SpeciesName.objects.filter(species_id=keep_id).exclude(name="")
                .values_list("kinetic_model", flat=True))
    db.SpeciesName.objects.filter(species_id=keep_id, name="", kinetic_model__in=named).delete()
    keep_oldest(db.Efficiency, ("kinetics", "species"), species_id=keep_id)
    merge_identical_thermo(keep_id)
    return reactions


def keep_oldest_names(species_id):
    """One name row per model and name of the record: the links of a second copy move to the
    oldest before it goes."""
    first = {}
    for pk, model, name in db.SpeciesName.objects.filter(species_id=species_id).order_by("pk").values_list(
            "pk", "kinetic_model", "name"):
        if (model, name) in first:
            move_references(db.SpeciesName, [pk], first[(model, name)])
            db.SpeciesName.objects.filter(pk=pk).delete()
        else:
            first[(model, name)] = pk


def merge_identical_thermo(species_id):
    """Model thermo rows of the record with the same polynomials become one, the oldest: the row
    the importer finds for them (model_thermo). Returns the rows merged away."""
    fields = ("coeffs_poly1", "coeffs_poly2", "temp_min_1", "temp_max_1", "temp_min_2", "temp_max_2")
    rows = defaultdict(list)
    for row in db.Thermo.objects.filter(species_id=species_id, provider_record__isnull=True).order_by(
            "pk").values("pk", *fields):
        rows[tuple(tuple(v) if isinstance(v, list) else v for v in (row[f] for f in fields))].append(row["pk"])
    merged = 0
    for ids in rows.values():
        if len(ids) > 1:
            move_references(db.Thermo, ids[1:], ids[0])
            db.Thermo.objects.filter(pk__in=ids[1:]).delete()
            merged += len(ids) - 1
    if merged:
        keep_oldest(db.ThermoComment, ("kinetic_model", "thermo", "species_name"), thermo__species_id=species_id)
    return merged


def link_names(link_ids):
    """kinetics link id -> the later names it writes, sorted (reactant, name) pairs."""
    names = defaultdict(list)
    for link_id, reactant, name in db.KineticsCommentName.objects.filter(
            kinetics_comment__in=link_ids).values_list("kinetics_comment_id", "reactant", "species_name__name"):
        names[link_id].append((reactant, name))
    return {link_id: tuple(sorted(v)) for link_id, v in names.items()}


def keep_oldest_links(kinetics_id):
    """One link per model and later names on a kinetics row: furop1 + H and furop2 + H with
    one rate are two of the model's lines."""
    links = list(db.KineticsComment.objects.filter(kinetics_id=kinetics_id).order_by("pk")
                 .values_list("pk", "kinetic_model"))
    names = link_names([pk for pk, _ in links])
    seen, extra = set(), []
    for pk, model in links:
        key = (model, names.get(pk, ()))
        if key in seen:
            extra.append(pk)
        else:
            seen.add(key)
    db.KineticsComment.objects.filter(pk__in=extra).delete()
    return len(extra)


def merge_kinetics(keep_id, drop_id):
    """Merge a kinetics row into the identical one of the same reaction."""
    move_references(db.Kinetics, [drop_id], keep_id)
    keep_oldest_links(keep_id)
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
    with transaction.atomic():
        report = merge_groups(split_groups(), log)
        if not apply:
            transaction.set_rollback(True)
    return dict(report)


def merge_groups(groups, log=print, report=None):
    """Merge each group of records into its first; see merge_split_species. Returns the counts."""
    report = Counter() if report is None else report
    report["split_groups"] += len(groups)
    report["records_merged_away"] += sum(len(g) - 1 for g in groups)
    reactions = set()
    for n, ids in enumerate(groups, 1):
        reactions |= merge_species_group(ids)
        if n % 100 == 0:
            log(f"  merged {n} of {len(groups)} groups")
    report["reactions_with_changed_species"] += len(reactions)
    # A collider efficiency on a merged record changes the rate's fingerprint.
    refresh_efficiencies_hashes(set(db.Efficiency.objects.filter(
        species_id__in=[ids[0] for ids in groups]).values_list("kinetics_id", flat=True)), report)
    merge_reactions(reactions, report)
    return report


# ---------------------------------------------------------------------------
# Variant records (Species.variant, Nov 2026)
# ---------------------------------------------------------------------------

def variant_column():
    """Whether database_species still has the variant column (migration 0021 removes it)."""
    from django.db import connection
    with connection.cursor() as cursor:
        return "variant" in {c.name for c in connection.introspection.get_table_description(
            cursor, db.Species._meta.db_table)}


def variant_records():
    """[(species id, model name, label)] of the records that 0019 gave a model's later name for a
    structure it already lists ("<model name>: <label>")."""
    from django.db import connection
    if not variant_column():
        return []
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id, variant FROM {db.Species._meta.db_table} WHERE variant <> '' ORDER BY id")
        rows = cursor.fetchall()
    return [(pk, *variant.split(": ", 1)) for pk, variant in rows]


def fold_species_variants(apply=False, log=print):
    """Merges each variant record into the record of its structure and state, and keeps its name,
    thermo links and kinetics links. Before anything moves, the links say which name they are for:
    the model's thermo links of both records name their record's name (ThermoComment.species_name),
    and each kinetics link of the model on a reaction of the variant record names the variant
    label each time it writes it (KineticsCommentName). Then the variant is cleared and the records
    are merged as merge_split_species merges them (reactions that become identical are merged, a
    link per model and names kept). A variant record without such a record becomes the shared
    record. Returns the counts; writes only with apply=True."""
    report = Counter()
    with transaction.atomic():
        variants = variant_records()
        report["variant_records"] = len(variants)
        if not variants:
            return dict(report)
        model_ids = dict(db.KineticModel.objects.values_list("model_name", "pk"))
        identity = species_identities()
        holders = defaultdict(set)
        variant_ids = {pk for pk, _, _ in variants}
        for species_id, (keys, state) in identity.items():
            if species_id not in variant_ids:
                for key in keys:
                    holders[(key, state)].add(species_id)
        for pk, model_name, label in variants:
            model_id = model_ids.get(model_name)
            names = db.SpeciesName.objects.filter(species_id=pk, kinetic_model_id=model_id, name=label)
            name = names.order_by("pk").first()
            if model_id is None or name is None:
                report["variants_without_their_name"] += 1
                log(f"  record {pk}: no name {label!r} of {model_name!r}")
                continue
            keys, state = identity.get(pk, (frozenset(), ""))
            shared = sorted(set().union(*(holders[(key, state)] for key in keys))) if keys else []
            if not shared:
                report["variants_without_shared_record"] += 1
                log(f"  record {pk} ({model_name}: {label}) has no shared record: it becomes one")
            # The thermo links of the variant record are its name's ...
            report["thermo_links_named"] += db.ThermoComment.objects.filter(
                kinetic_model_id=model_id, thermo__species_id=pk).update(species_name=name)
            # ... and those of the shared record in this model are its own name's, its first name.
            for other in shared:
                first = db.SpeciesName.objects.filter(species_id=other, kinetic_model_id=model_id).exclude(
                    name="").order_by("pk").first()
                if first is not None:
                    report["thermo_links_named"] += db.ThermoComment.objects.filter(
                        kinetic_model_id=model_id, thermo__species_id=other).update(species_name=first)
            # Each time a kinetics link of the model writes the variant record, it writes the label.
            coefficients = defaultdict(list)
            for reaction_id, coeff in db.Stoichiometry.objects.filter(species_id=pk).values_list("reaction_id", "coeff"):
                coefficients[reaction_id].append(coeff)
            rows = []
            for link_id, reaction_id in db.KineticsComment.objects.filter(
                    kinetic_model_id=model_id, kinetics__reaction_id__in=list(coefficients)).values_list(
                    "pk", "kinetics__reaction_id"):
                for coeff in coefficients[reaction_id]:
                    if coeff != int(coeff):
                        report["fractional_coefficients_not_named"] += 1
                        continue
                    rows += [db.KineticsCommentName(kinetics_comment_id=link_id, species_name=name,
                                                    reactant=coeff < 0) for _ in range(abs(int(coeff)))]
            db.KineticsCommentName.objects.bulk_create(rows)
            report["kinetics_names_written"] += len(rows)
            report["kinetics_links_named"] += len({row.kinetics_comment_id for row in rows})
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {db.Species._meta.db_table} SET variant = '' WHERE variant <> ''")
        groups = [g for g in split_groups() if variant_ids & set(g)]
        # The shared record is kept: the oldest record that is not a variant record first.
        groups = [sorted(g, key=lambda sp: (sp in variant_ids, g.index(sp))) for g in groups]
        merge_groups(groups, log, report)
        # A variant record that is the only record of its structure keeps its rows; its hash
        # loses the variant, or it joins the record that already has that hash.
        for species in db.Species.objects.filter(pk__in=variant_ids).order_by("pk"):
            new_hash = get_species_hash(species.isomers.all(), species.electronic_state)
            twin = db.Species.objects.filter(hash=new_hash).exclude(pk=species.pk).values_list("pk", flat=True).first()
            if twin is not None:
                merge_groups([[twin, species.pk]], log, report)
            else:
                db.Species.objects.filter(pk=species.pk).update(hash=new_hash)
                report["variant_records_kept_as_shared"] += 1
        report["species_records_after"] = db.Species.objects.count()
        if not apply:
            transaction.set_rollback(True)
    return dict(report)


# ---------------------------------------------------------------------------
# Model links
# ---------------------------------------------------------------------------

def model_links(model):
    """The model's names, thermo links (with the name each is for, "" for a record's only name)
    and kinetics links (with the later names each writes, see link_names)."""
    kinetics = list(db.KineticsComment.objects.filter(kinetic_model=model)
                    .values("id", "kinetics_id", "kinetics__reaction_id", "kinetics__reaction__canonical_key",
                            "comment", "reversible"))
    names = link_names([k["id"] for k in kinetics])
    for k in kinetics:
        k["names"] = names.get(k.pop("id"), ())
    thermo = list(db.ThermoComment.objects.filter(kinetic_model=model)
                  .values("thermo_id", "thermo__species_id", "comment", "species_name__name"))
    for t in thermo:
        t["name"] = t.pop("species_name__name") or ""
    return (
        list(db.SpeciesName.objects.filter(kinetic_model=model).values("species_id", "name")),
        thermo,
        kinetics,
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


# The equation a kinetics link's comment names: "The chemkin file reaction is A + B <=> C" from
# the CHEMKIN conversion, "AutoTST M062X for A + B <=> C" from AutoTST.
COMMENT_EQUATION = re.compile(r"(?:chemkin file reaction is|M062X for)\s+(.+)$", re.I)


def comment_equation(comment):
    """The two sides of the equation a link's comment names, as lists of tokens ("2OH",
    "CH2(S)"), or None when it names none. Fall-off and third-body partners ((+M), + M) are
    left out."""
    match = COMMENT_EQUATION.search((comment or "").split("\n")[0])
    sides = re.split(r"\s*(?:<=>|=>|=)\s*", match.group(1).strip(), maxsplit=1) if match else []
    if len(sides) != 2:
        return None
    return [[t for t in re.split(r"\s+\+\s+", re.sub(r"\(\+[^)]*\)", "", side).strip()) if t and t.upper() != "M"]
            for side in sides]


def writes_equation(stoichiometry, names, equation):
    """Whether the reaction, rows of (species id, coeff), written with the model's names (species
    id -> names), is `equation` from comment_equation, in either direction. None when the
    equation uses a name the model does not have, so it cannot tell."""
    lower = {species: {n.lower() for n in v} for species, v in names.items()}
    known = set().union(*lower.values()) if lower else set()
    sides = []
    for tokens in equation:
        side = Counter()
        for token in (t.lower() for t in tokens):
            count = re.match(r"(\d+)\s*(.+)$", token)
            if token in known:
                side[token] += 1
            elif count and count.group(2) in known:  # 2OH
                side[count.group(2)] += int(count.group(1))
            else:
                return None
        sides.append(side)

    def fits(rows, wanted):
        # Gives each species one of its names so that the names add up to `wanted`.
        if not rows:
            return not +wanted
        (species, coeff), rest = rows[0], rows[1:]
        for name in lower.get(species, ()):
            if wanted[name] >= coeff:
                wanted[name] -= coeff
                if fits(rest, wanted):
                    return True
                wanted[name] += coeff
        return False

    def units(rows):
        # 2 OH is OH + OH, so that a record with two names may be written OH + OHV.
        return [(s, 1) for s, c in rows for _ in range(int(c))] if all(c == int(c) for s, c in rows) else rows

    reactants = units([(s, -c) for s, c in stoichiometry if c < 0])
    products = units([(s, c) for s, c in stoichiometry if c > 0])
    return any(fits(reactants, Counter(left)) and fits(products, Counter(right))
               for left, right in (sides, sides[::-1]))


def stoichiometry_rows(reaction_ids=None):
    """reaction id -> [(species id, coeff)], for every reaction when reaction_ids is None."""
    rows = db.Stoichiometry.objects.all()
    if reaction_ids is not None:
        rows = rows.filter(reaction_id__in=reaction_ids)
    out = defaultdict(list)
    for reaction_id, species_id, coeff in rows.values_list("reaction_id", "species_id", "coeff"):
        out[reaction_id].append((species_id, coeff))
    return out


def links_not_their_equation(links, names, stoichiometry):
    """The kinetics links (rows with kinetics__reaction_id and comment) whose reaction, written
    with the model's names, is not the equation their comment names."""
    return [k for k in links
            if (equation := comment_equation(k["comment"]))
            and writes_equation(stoichiometry[k["kinetics__reaction_id"]], names, equation) is False]


def mismatched_kinetics_links():
    """The kinetics links of every model whose reaction is not the equation their comment names:
    links an older import made before the clean-up corrected a species, e.g. ch2(s) <=> ch2 on a
    CH2(T) = CH2(T) reaction. rebuild_model_links kept them because their model's library does
    not import whole."""
    names = defaultdict(lambda: defaultdict(set))
    for model_id, species_id, name in db.SpeciesName.objects.exclude(kinetic_model=None).values_list(
            "kinetic_model_id", "species_id", "name"):
        if name:
            names[model_id][species_id].add(name)
    stoichiometry = stoichiometry_rows()
    links = defaultdict(list)
    for k in db.KineticsComment.objects.values(
            "id", "kinetic_model_id", "kinetic_model__model_name", "kinetics_id", "kinetics__reaction_id", "comment"):
        links[k["kinetic_model_id"]].append(k)
    return [k for model_id, rows in links.items()
            for k in links_not_their_equation(rows, names[model_id], stoichiometry)]


def prune_mismatched_links(apply=False):
    """Deletes the links mismatched_kinetics_links() finds and returns them. Their kinetics,
    reactions and species are left to prune_unlinked_rows."""
    with transaction.atomic():
        rows = mismatched_kinetics_links()
        db.KineticsComment.objects.filter(pk__in=[k["id"] for k in rows]).delete()
        if not apply:
            transaction.set_rollback(True)
    return rows


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
    counts = {k: v for k, v in counts.items() if k in ("imported", "failed", "rejected", "moved_terms", "added_lines")}
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
    # A link is its row and the name it is for: two names may share a thermo row or a rate.
    thermo_key, kinetics_key = (lambda t: (t["thermo_id"], t["name"])), (lambda k: (k["kinetics_id"], k["names"]))
    made_thermo = set(map(thermo_key, made[1]))
    covered = {t["thermo__species_id"] for t in made[1]}
    covered_names = set().union(*(made_names_of[s] for s in covered)) if covered else set()
    keep_thermo = {thermo_key(t): t for t in old[1]
                   if thermo_key(t) not in made_thermo and thermo_status != "ok"
                   and t["thermo__species_id"] not in covered
                   and not old_names[t["thermo__species_id"]] & covered_names}
    made_kinetics = set(map(kinetics_key, made[2]))
    made_reactions = {k["kinetics__reaction__canonical_key"] for k in made[2]} - {""}
    made_equations = set().union(*label_equations(made[2], made_names_of).values())
    old_equations = label_equations(old[2], old_names)
    keep_kinetics = {kinetics_key(k): k for k in old[2]
                     if kinetics_key(k) not in made_kinetics and kinetics_status != "ok"
                     and k["kinetics__reaction__canonical_key"] not in made_reactions
                     and not old_equations[k["kinetics_id"]] & made_equations}
    # A kept link must still be the equation it names, written with the names the model has
    # now: an old link on a species the clean-up corrected (ch2(s) <=> ch2 on CH2(T) = CH2(T)) goes.
    names_now = names_of_species(made[0] + [{"species_id": s, "name": n} for s, n in keep_names])
    stoichiometry = stoichiometry_rows({k["kinetics__reaction_id"] for k in keep_kinetics.values()})
    wrong = links_not_their_equation(keep_kinetics.values(), names_now, stoichiometry)
    for k in wrong:
        del keep_kinetics[kinetics_key(k)]
    result["kinetics_links_not_their_equation"] = len(wrong)
    db.SpeciesName.objects.bulk_create([
        db.SpeciesName(species_id=species, kinetic_model=model, name=name) for species, name in keep_names])
    # Kept links name the model's name rows as they are now.
    name_rows, first_row = {}, {}
    for pk, species, name in db.SpeciesName.objects.filter(kinetic_model=model).order_by("pk").values_list(
            "pk", "species_id", "name"):
        name_rows.setdefault((species, name), pk)
        first_row.setdefault(name, pk)
    db.ThermoComment.objects.bulk_create([
        db.ThermoComment(thermo_id=t["thermo_id"], kinetic_model=model, comment=t["comment"],
                         species_name_id=name_rows.get((t["thermo__species_id"], t["name"])) if t["name"] else None)
        for t in keep_thermo.values()])
    # A kept link keeps its arrow too: its library entry failed, so nothing can set it again.
    kept_links = db.KineticsComment.objects.bulk_create([
        db.KineticsComment(kinetics_id=k["kinetics_id"], kinetic_model=model, comment=k["comment"][:1000],
                           reversible=k["reversible"])
        for k in keep_kinetics.values()])
    db.KineticsCommentName.objects.bulk_create([
        db.KineticsCommentName(kinetics_comment=link, species_name_id=first_row[name], reactant=reactant)
        for link, k in zip(kept_links, keep_kinetics.values()) for reactant, name in k["names"]
        if name in first_row])

    # Counts compare the link rows before and after: a second copy of a link counts as removed.
    after = model_links(model)
    keys = (lambda n: (n["species_id"], n["name"]), thermo_key, kinetics_key)
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

    r["thermo_links_duplicate"] = duplicate_rows(db.ThermoComment, ("kinetic_model", "thermo", "species_name"))
    # A link is one per model, kinetics row and later names (furop1 + H and furop2 + H, one rate).
    link_rows = list(db.KineticsComment.objects.values_list("pk", "kinetic_model", "kinetics"))
    written = link_names([pk for pk, _, _ in link_rows])
    r["kinetics_links_duplicate"] = sum(n - 1 for n in Counter(
        (model, kinetics, written.get(pk, ())) for pk, model, kinetics in link_rows).values() if n > 1)
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
    # A model's two names for one record (furop1 and furop2): each thermo link of the record in
    # that model names one of them, no name has two, and each name a kinetics link writes is a
    # name of that model for a species on that side of the reaction.
    r["variant_species_records"] = len(variant_records())
    thermo_links = list(db.ThermoComment.objects.values_list("kinetic_model", "thermo__species_id", "species_name"))
    per_record = Counter((m, s) for m, s, _ in thermo_links)
    r["thermo_links_without_name_on_records_with_2plus"] = sum(
        1 for m, s, name in thermo_links if per_record[(m, s)] > 1 and name is None)
    r["names_with_2plus_thermo_links"] = sum(
        n - 1 for n in Counter(name for _, _, name in thermo_links if name is not None).values() if n > 1)
    sides = defaultdict(Counter)
    for reaction_id, species_id, coeff in db.Stoichiometry.objects.values_list("reaction_id", "species_id", "coeff"):
        sides[reaction_id][(species_id, coeff < 0)] += abs(coeff)
    written_names = defaultdict(Counter)
    wrong_model = 0
    for link_id, reaction_id, reactant, species_id, name_model, link_model in db.KineticsCommentName.objects.values_list(
            "kinetics_comment_id", "kinetics_comment__kinetics__reaction_id", "reactant", "species_name__species_id",
            "species_name__kinetic_model_id", "kinetics_comment__kinetic_model_id"):
        written_names[(link_id, reaction_id)][(species_id, reactant)] += 1
        wrong_model += name_model != link_model
    r["kinetics_names_of_another_model"] = wrong_model
    r["kinetics_names_not_on_their_reaction"] = sum(
        1 for (link_id, reaction_id), counts in written_names.items()
        if any(n > sides[reaction_id][key] for key, n in counts.items()))
    mismatched = mismatched_kinetics_links()
    r["kinetics_links_not_their_equation"] = len(mismatched)
    r["examples"] = {
        "kinetics_links_not_their_equation": [
            (k["kinetic_model__model_name"], k["comment"][:80]) for k in mismatched[:5]],
        "split_species": [g[:4] for g in groups[:5]],
        "model_names_on_2plus_records": [
            (db.KineticModel.objects.get(pk=m).model_name, n, sorted(v))
            for (m, n), v in list((k, v) for k, v in records_of.items() if len(v) > 1)[:5]],
    }
    return r
