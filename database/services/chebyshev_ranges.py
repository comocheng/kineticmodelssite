"""Give each model's Chebyshev rates the model's own T and P range.

A Chebyshev rate's range makes its reduced T and P, so the same coefficients with another range
are another k. Before the range was part of the record's identity (kinetic_data.range_identity),
the importer gave a model that writes the coefficients of an earlier model with another range the
earlier model's record and range: PCI2017/111-Jin's TCHEB 270 3000 rates carry 290 3000 from
CombFlame2013/1939-Cai, up to a factor of 5 in k.

For each link to a Chebyshev record, the model's own range is the one the importer stores: that of
its RMG-models library entry (<path>/<model>/RMG-Py-kinetics-library/reactions.py; the entry of the
same reaction by the model's species names, the same collider and the same coefficients), with the
PCHEB of the model's CHEMKIN line where the library's is that number written with 6 digits
(author_digits.is_rounding: 0.009869232667160128 atm, not 0.00986923). The links of a record whose
models give two or more ranges are split: the links with the stored range stay, the others go to
the record of their range (an existing one, or a copy of the record with that range, its
efficiencies and its own rate fingerprint). A record none of whose models has the stored range
takes the range of most of its links (or, when another record has that range, its links go there
and a record left without links is deleted). A link without a library entry stays where it is and
is reported. The link rows move, so each keeps its comment, arrow and reverse rate.
"""
import os
import re
from collections import Counter, defaultdict

from django.db import transaction

from database import models as db
from database.models.kinetic_data import RANGE_FIELDS, kinetics_identity
from database.scripts import author_digits, chemkin_lines
from database.scripts.import_rmg_models import (
    create_kinetics_data, get_base_kinetics_data_fields, index_new_rows, kinetics_local_context)
from database.services.cleanup import MODELS

LIBRARY = os.path.join("RMG-Py-kinetics-library", "reactions.py")
COLLIDER = re.compile(r"\s*\(\+\s*([^)]+)\)\s*$")
SAME = 1e-9


def chebyshev_entries(library_path):
    """(label, raw_data, range) of each Chebyshev entry of a library, as the importer makes them."""
    entries = []

    def entry(**fields):
        data = fields.get("kinetics")
        if type(data).__name__ == "Chebyshev":
            base = get_base_kinetics_data_fields(data)
            entries.append((fields["label"], create_kinetics_data(None, data, None),
                            tuple(base.get(name) for name in RANGE_FIELDS)))

    with open(library_path) as handle:
        code = compile(handle.read(), library_path, "exec")
    exec(code, {"__builtins__": __builtins__}, {**kinetics_local_context(), "entry": entry})
    return entries


def label_parts(label):
    """(reactant names, product names, collider name or None) of a library label."""
    arrow = "<=>" if "<=>" in label else "=>"
    sides, collider = [], None
    for side in label.split(arrow, 1):
        names = []
        for name in side.split(" + "):
            name = name.strip()
            found = COLLIDER.search(name)
            if found:
                collider = found.group(1).strip()
                name = name[:found.start()].strip()
            if name:
                names.append(name)
        sides.append(names)
    return sides[0], sides[1], None if collider in (None, "M") else collider


def same_numbers(a, b):
    """The same raw_data, numbers within SAME (PostgreSQL may give 1.0 back as 1)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_numbers(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_numbers(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= SAME * max(1.0, abs(a), abs(b))
    return a == b


def same_range(a, b):
    return all((x is None and y is None) or (x is not None and y is not None and abs(x - y) <= SAME * max(abs(x), abs(y)))
               for x, y in zip(a, b))


def stored_range(kinetics):
    return tuple(getattr(kinetics, name) for name in RANGE_FIELDS)


def _keys(names, left, right):
    """The (sorted reactant ids, sorted product ids) a label can be, in both directions."""
    def choices(side):
        out = [[]]
        for name in side:
            ids = names.get(name)
            if not ids:
                return []
            out = [prev + [i] for prev in out for i in sorted(ids)]
        return [tuple(sorted(ids)) for ids in out]
    a, b = choices(left), choices(right)
    return {(x, y) for x in a for y in b} | {(y, x) for x in a for y in b}


def chemkin_lines_of(model_dir, names):
    """The Chebyshev lines of the model's CHEMKIN file whose species the model has, read with every digit
    as author_digits reads them: [{"keys", "raw", "range", "collider", "taken"}]; [] without a file.
    `names` maps the model's names in upper case (CHEMKIN names are not case sensitive) to species ids."""
    from rmgpy.molecule import Molecule
    from rmgpy.species import Species

    path = chemkin_lines.reactions_file(model_dir)
    if not path:
        return []
    library = os.path.join(model_dir, LIBRARY)
    ea_to_j, molecules = chemkin_lines.units(path, library if os.path.exists(library) else None)
    units = chemkin_lines.rmg_units(ea_to_j, molecules)
    tokens = set(names) | chemkin_lines.species_names(path)
    species = {name: Species(label=name, molecule=[Molecule()]) for name in tokens}
    found = []
    for line in chemkin_lines.read_reactions(path, tokens, ea_to_j):
        heads = {body.split("/")[0].strip().upper() for body in line["entry"][1:]}
        if not heads & {"CHEB", "TCHEB", "PCHEB"}:
            continue
        left, right = ([n.upper() for n in line[side]] for side in ("reactants", "products"))
        if not all(names.get(n) for n in left + right):
            continue
        try:
            raw, base, collider = author_digits._author_rate(line, species, units)
        except Exception:
            continue
        if raw["type"] == "chebyshev":
            found.append({"keys": _keys(names, left, right), "raw": raw, "collider": collider, "taken": False,
                          "range": tuple(base.get(name) for name in RANGE_FIELDS)})
    return found


def _line_of(lines, key, kinetics):
    """The model's CHEMKIN line of this record's rate: the same species, collider and coefficients
    (within author_digits.MATCH)."""
    hits = []
    for line in lines:
        if key not in line["keys"] or (line["collider"] is None) != (kinetics.specific_collider_id is None):
            continue
        try:
            found = list(author_digits.leaves(line["raw"], kinetics.raw_data))
        except author_digits.Mismatch:
            continue
        if max((author_digits.rel(x, y) for _, x, y, _ in found), default=0.0) <= author_digits.MATCH:
            hits.append(line)
    line = next((h for h in hits if not h["taken"]), hits[0] if hits else None)
    if line is not None:
        line["taken"] = True
    return line


def own_ranges(path, models=None, notes=None):
    """[(link, own range or None, status)] for every link to a Chebyshev record; status is
    `paired`, `no_library` (no library file for the model), `library_not_read` or
    `no_library_entry`. `models` limits it to these model names. `notes` (a Counter) counts the
    PCHEB values taken from the CHEMKIN lines and the TCHEB values of a line that differ from the
    library's (the library's is kept)."""
    notes = Counter() if notes is None else notes
    links = defaultdict(list)
    for link in db.KineticsComment.objects.filter(kinetics__raw_data__type="chebyshev").select_related(
            "kinetic_model", "kinetics").order_by("pk"):
        if not models or link.kinetic_model.model_name in models:
            links[link.kinetic_model].append(link)
    sides = defaultdict(lambda: ([], []))
    reaction_ids = {link.kinetics.reaction_id for rows in links.values() for link in rows}
    for reaction_id, species_id, coeff in db.Stoichiometry.objects.filter(reaction_id__in=reaction_ids).values_list(
            "reaction_id", "species_id", "coeff"):
        sides[reaction_id][0 if coeff < 0 else 1].extend([species_id] * int(round(abs(coeff))))
    out = []
    for model, rows in sorted(links.items(), key=lambda item: item[0].model_name):
        library = os.path.join(path, model.model_name, LIBRARY)
        if not os.path.exists(library):
            out.extend((link, None, "no_library") for link in rows)
            continue
        try:
            entries = chebyshev_entries(library)
        except Exception:
            out.extend((link, None, "library_not_read") for link in rows)
            continue
        names, upper = defaultdict(set), defaultdict(set)
        for name, species_id in db.SpeciesName.objects.filter(kinetic_model=model).values_list("name", "species_id"):
            names[name].add(species_id)
            if name:
                upper[name.upper()].add(species_id)
        lines = chemkin_lines_of(os.path.join(path, model.model_name), upper)
        candidates = []
        for label, raw, own in entries:
            left, right, collider = label_parts(label)
            candidates.append({"keys": _keys(names, left, right), "raw": raw, "range": own, "taken": False,
                               "collider": names.get(collider, set()) if collider else {None}})
        for link in rows:
            kinetics = link.kinetics
            key = tuple(tuple(sorted(side)) for side in sides[kinetics.reaction_id])
            hits = [c for c in candidates if key in c["keys"] and kinetics.specific_collider_id in c["collider"]
                    and same_numbers(c["raw"], kinetics.raw_data)]
            hit = next((c for c in hits if not c["taken"]), hits[0] if hits else None)
            if hit is None:
                out.append((link, None, "no_library_entry"))
                continue
            hit["taken"] = True
            own = list(hit["range"])
            line = _line_of(lines, key, kinetics)
            if line is not None:
                for index, name in enumerate(RANGE_FIELDS):
                    author, library_value = line["range"][index], own[index]
                    if author is None or library_value is None:
                        continue
                    if name.endswith("pressure") and author_digits.is_rounding(author, library_value, author_digits.ATM):
                        own[index] = author
                        notes["pcheb_authors_digits"] += 1
                    elif author_digits.rel(author, library_value) > author_digits.EXACT:
                        notes[f"line_differs_from_library_{name}"] += 1
            out.append((link, tuple(own), "paired"))
    return out


def _copy(kinetics, own):
    """A copy of a record with another range, its efficiencies and its own fingerprint."""
    copy = db.Kinetics.objects.create(
        prime_id=kinetics.prime_id, reaction_id=kinetics.reaction_id, source_id=kinetics.source_id,
        relative_uncertainty=kinetics.relative_uncertainty, reverse=kinetics.reverse, raw_data=kinetics.raw_data,
        specific_collider_id=kinetics.specific_collider_id, efficiencies_hash=kinetics.efficiencies_hash,
        **dict(zip(RANGE_FIELDS, own)))
    db.Efficiency.objects.bulk_create([
        db.Efficiency(kinetics=copy, species_id=species_id, efficiency=efficiency)
        for species_id, efficiency in kinetics.efficiency_set.values_list("species_id", "efficiency")])
    index_new_rows(MODELS, kinetics=copy)
    return copy


def _range_text(values):
    tmin, tmax, pmin, pmax = values
    text = f"{tmin:g}-{tmax:g} K" if tmin is not None else "no T range"
    return text + (f", {pmin / 101325:.6g}-{pmax / 101325:.6g} atm" if pmin is not None else "")


def split_chebyshev_ranges(path, apply=False, models=None):
    """Split the Chebyshev records whose models give other ranges (see the module). Without
    `apply` the work is done and rolled back. Returns the counts and one row per changed record."""
    report = Counter()
    rows, unpaired = [], []
    with transaction.atomic():
        by_record = defaultdict(list)
        notes = Counter()
        for link, own, status in own_ranges(path, models, notes):
            report[f"links_{status}"] += 1
            by_record[link.kinetics_id].append((link, own))
            if own is None:
                unpaired.append({"model": link.kinetic_model.model_name, "link_id": link.pk,
                                 "kinetics_id": link.kinetics_id, "status": status})
        report["records"] = len(by_record)
        for kinetics_id, members in sorted(by_record.items()):
            kinetics = db.Kinetics.objects.get(pk=kinetics_id)
            stored = stored_range(kinetics)
            groups = []  # [range, links]
            for link, own in members:
                if own is None:
                    continue
                group = next((g for g in groups if same_range(g[0], own)), None)
                if group is None:
                    groups.append([own, [link]])
                else:
                    group[1].append(link)
            keep = next((g for g in groups if same_range(g[0], stored)), None)
            if len(groups) < 2 and (keep is not None or not groups):
                continue
            row = {"kinetics_id": kinetics_id, "stored": _range_text(stored), "kept": None, "moved": []}
            if keep is None:
                # No model has the stored range: the record takes that of most of its links,
                # unless another record already has it (then those links move there too).
                largest = max(groups, key=lambda g: (len(g[1]), -min(link.pk for link in g[1])))
                identity = kinetics_identity(kinetics, **dict(zip(RANGE_FIELDS, largest[0])))
                if not db.Kinetics.objects.filter(**identity).exclude(pk=kinetics.pk).exists():
                    keep = largest
                    db.Kinetics.objects.filter(pk=kinetics.pk).update(**dict(zip(RANGE_FIELDS, keep[0])))
                    kinetics.refresh_from_db()
                    index_new_rows(MODELS, kinetics=kinetics)
                    row["range_changed_to"] = _range_text(keep[0])
                    report["records_with_changed_range"] += 1
            if keep is not None:
                row["kept"] = {"range": _range_text(keep[0]),
                               "models": sorted(link.kinetic_model.model_name for link in keep[1])}
            for group in groups:
                if group is keep:
                    continue
                own, links = group
                target = db.Kinetics.objects.filter(**kinetics_identity(kinetics, **dict(zip(RANGE_FIELDS, own)))).exclude(
                    pk=kinetics.pk).first()
                new = target is None
                if new:
                    target = _copy(kinetics, own)
                    report["records_created"] += 1
                else:
                    report["links_moved_to_existing_records"] += len(links)
                db.KineticsComment.objects.filter(pk__in=[link.pk for link in links]).update(kinetics=target)
                report["links_moved"] += len(links)
                row["moved"].append({"range": _range_text(own), "to": target.pk, "new": new,
                                     "models": sorted(link.kinetic_model.model_name for link in links)})
            if not db.KineticsComment.objects.filter(kinetics=kinetics).exists():
                # Every link went to a record of its range: nothing uses this one (Efficiency rows go with it).
                kinetics.delete()
                row["deleted"] = True
                report["records_deleted"] += 1
            report["records_changed"] += 1
            rows.append(row)
        if not apply:
            transaction.set_rollback(True)
    return {"counts": dict(sorted(report.items())), "notes": dict(sorted(notes.items())), "records": rows,
            "links_without_own_range": unpaired}
