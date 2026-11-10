"""The authors' digits: each rate number as the model's CHEMKIN line writes it.

RMG-models wrote its RMG-Py libraries with ScalarQuantity.__repr__ ('{0:g}', 6 significant digits), and the
importer stores the library's numbers, so PCI2017/051-Pelucchi's Ea 45025.57 cal/mol was 45025.6. Of the
690,033 numbers of the authors' lines in local kms on 4 Nov 2026, 13,031 in 69 models were rounded so
(cleanup_evidence/author_digits). Here each line of the model's CHEMKIN file (the --reactions file of its
import.sh, chemkin_lines.read_reactions) is read again with RMG-Py's CHEMKIN reader, with every digit, and
paired with one rate term of the model's links: the same species records in the same direction (the model's
SpeciesName rows), the same collider, the same kind of rate, and each number within 2e-5. A DUPLICATE line is
one term of a multi-rate; each term is taken once.

A stored number that is the author's number written with '{0:g}' becomes the author's number; any other
difference keeps the stored one. So do the Chebyshev pressure range (PCHEB) and nothing else: collider
efficiencies and TROE alpha were written with every digit, and Chebyshev coefficients were not rounded.

A record of several models keeps its raw_data for the models whose lines give it. Models whose authors wrote
more digits move to the record that has their numbers, or to a new one (copied with its efficiencies); a
record that no model keeps takes the numbers of most of its models. RMG-models is only read.
"""
import copy
import json
import logging
import math
import os
from collections import Counter, defaultdict
from itertools import product

from django.db import transaction

from database.models.kinetic_data import kinetics_identity, range_identity
from database.scripts import chemkin_lines

logger = logging.getLogger(__name__)

MATCH = 2e-5            # 6-digit rounding moves a number by at most 5e-6 of it
EXACT = 1e-12
ATM = 101325.0          # a PLOG or PCHEB pressure is stored in Pa; RMG-models wrote it in atm
ULPS = 8                # RMG's unit round trip (cm to m, cal to J) moves a value by at most 3.4 ulp
BASE_FIELDS = ("min_temp", "max_temp", "min_pressure", "max_pressure")


class Mismatch(Exception):
    """The line and the stored term are not the same kind of rate."""


def can_restore(models):
    """Only with the current models: an old data migration imports with historical ones."""
    from database.models import Kinetics
    return getattr(models, "Kinetics", None) is Kinetics


def rel(a, b):
    return 0.0 if a == b else abs(a - b) / max(abs(a), abs(b))


def is_rounding(author, stored, factor=1.0):
    """Whether *stored* is *author* (in the unit RMG-models wrote: stored / factor) written with '{0:g}'."""
    return rel(author, stored) > EXACT and rel(float(f"{author / factor:g}"), stored / factor) <= EXACT


def decimal(value):
    """The shortest decimal within ULPS of *value*: 43950.169 for RMG's 43950.16900000001."""
    for digits in range(1, 18):
        text = format(value, f".{digits}g")
        if abs(float(text) - value) <= ULPS * math.ulp(value):
            return float(text)
    return value


def terms(raw):
    """The rate terms of a raw_data, one per CHEMKIN line."""
    if raw["type"] == "multi_arrhenius":
        return raw["arrhenius_set"]
    if raw["type"] == "multi_pdep_arrhenius":
        return raw["pdep_arrhenius_set"]
    return [raw]


def _arrhenius_leaves(prefix, a, s):
    if a.get("type") != s.get("type"):
        raise Mismatch
    if a["type"] == "multi_arrhenius":
        if len(a["arrhenius_set"]) != len(s["arrhenius_set"]):
            raise Mismatch
        for x, y in zip(a["arrhenius_set"], s["arrhenius_set"]):
            yield from _arrhenius_leaves(prefix, x, y)
        return
    if a["a_units"] != s["a_units"]:
        raise Mismatch
    yield f"{prefix}A", a["a"], s["a"], 1.0
    yield f"{prefix}n", a["n"], s["n"], 1.0
    if a["e_units"] == s["e_units"]:
        yield f"{prefix}Ea", a["e"], s["e"], 1.0
    else:
        yield f"{prefix}Ea", a["e_si"], s["e_si"], 1.0


def leaves(author, stored):
    """(parameter, author value, stored value, factor to the unit RMG-models wrote) of each number of a
    term; Mismatch when the two are not the same kind of rate."""
    kind = author["type"]
    if kind != stored["type"]:
        raise Mismatch
    if kind == "arrhenius":
        yield from _arrhenius_leaves("", author, stored)
    elif kind == "third_body":
        yield from _arrhenius_leaves("", author["low_arrhenius"], stored["low_arrhenius"])
    elif kind in ("lindemann", "troe"):
        yield from _arrhenius_leaves("", author["high_arrhenius"], stored["high_arrhenius"])
        yield from _arrhenius_leaves("LOW ", author["low_arrhenius"], stored["low_arrhenius"])
        if kind == "troe":
            yield "TROE alpha", author["alpha"], stored["alpha"], 1.0
            for key in ("t3", "t1", "t2"):
                yield f"TROE {key.upper()}", author.get(key) or 0.0, stored.get(key) or 0.0, 1.0
    elif kind == "pdep_arrhenius":
        if len(author["pressure_set"]) != len(stored["pressure_set"]):
            raise Mismatch
        for x, y in zip(author["pressure_set"], stored["pressure_set"]):
            yield "PLOG P", x["pressure"], y["pressure"], ATM
            yield from _arrhenius_leaves("PLOG ", x["arrhenius"], y["arrhenius"])
    elif kind == "chebyshev":
        ma, ms = author["coefficient_matrix"], stored["coefficient_matrix"]
        if author["units"] != stored["units"] or len(ma) != len(ms) or any(len(x) != len(y) for x, y in zip(ma, ms)):
            raise Mismatch
        for x, y in zip(ma, ms):
            for u, v in zip(x, y):
                yield "CHEB coefficient", u, v, 1.0
    else:
        raise Mismatch


def restored(author, stored, key=None):
    """*stored* with each number that is the author's written with '{0:g}' replaced by the author's."""
    if isinstance(stored, dict):
        out = dict(stored)
        if stored.get("type") == "arrhenius":
            for name, si in (("a", "a_si"), ("e", "e_si")):
                same_unit = name == "a" or author.get("e_units") == stored.get("e_units")
                if same_unit and is_rounding(author[name], stored[name]):
                    out[name], out[si] = decimal(author[name]), author[si]
            if is_rounding(author["n"], stored["n"]):
                out["n"] = author["n"]
            return out
        for name, value in stored.items():
            if name in author and name != "type":
                out[name] = restored(author[name], value, name)
        return out
    if isinstance(stored, list):
        return [restored(a, s, key) for a, s in zip(author, stored)]
    if isinstance(stored, (int, float)) and not isinstance(stored, bool) and isinstance(author, (int, float)):
        return float(author) if is_rounding(float(author), float(stored), ATM if key == "pressure" else 1.0) \
            else stored
    return stored


def canonical(raw):
    """A raw_data as text, numbers as floats: PostgreSQL keeps 1.233e66 as an integer."""
    def floats(value):
        if isinstance(value, dict):
            return {k: floats(v) for k, v in value.items()}
        if isinstance(value, list):
            return [floats(v) for v in value]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return value
    return json.dumps(floats(raw), sort_keys=True)


def _author_rate(line, species, units):
    """The line read with RMG-Py's CHEMKIN reader as the importer's raw_data, its base fields and its
    specific collider (upper case); collider efficiencies are left out (line_efficiencies)."""
    from rmgpy.chemkin import read_kinetics_entry

    from database.scripts.import_rmg_models import create_kinetics_data, get_base_kinetics_data_fields
    a_units, ea_units = units
    if ea_units is None:
        raise ValueError("an Ea unit RMG-Py cannot read")
    reaction = read_kinetics_entry(chemkin_lines.kinetics_entry(line, set()), species, a_units, [], ea_units)
    collider = getattr(reaction, "specific_collider", None)
    return (create_kinetics_data(None, reaction.kinetics, None), get_base_kinetics_data_fields(reaction.kinetics),
            collider.label.upper() if collider is not None else None)


def line_efficiencies(line):
    """{upper-case name: efficiency} of a line. read_reactions takes a line commented out with // (Somers
    2291) for an auxiliary line of the reaction above it; those are left out."""
    found = {}
    for body in line["entry"][1:]:
        first = body.split("/")[0].split()
        if body.startswith("//") or (first and first[0].upper() in chemkin_lines.AUX):
            continue
        for name, value in chemkin_lines.EFFICIENCY.findall(body.upper()):
            try:
                found.setdefault(name, float(value.replace("D", "E")))
            except ValueError:
                pass
    return found


def model_changes(kinetic_model, model_dir, models):
    """The model's links with the authors' digits: {"links": {link id: (raw_data, base fields)} for each link
    whose numbers change, "status": Counter of the lines (paired, no_species, no_stored_rate,
    rmg_cannot_read), "numbers": Counter per parameter of the numbers that change, "other": numbers that
    differ by more than the rounding (kept)}."""
    from rmgpy.molecule import Molecule
    from rmgpy.species import Species

    report = {"model": kinetic_model.model_name, "links": {}, "status": Counter(), "numbers": Counter(),
              "other": Counter()}
    path = chemkin_lines.reactions_file(model_dir) if model_dir and os.path.isdir(model_dir) else None
    if not path:
        return report
    links = list(models.KineticsComment.objects.filter(kinetic_model=kinetic_model)
                 .select_related("kinetics").order_by("id"))
    names = defaultdict(set)
    for name, species_id in models.SpeciesName.objects.filter(kinetic_model=kinetic_model) \
            .exclude(name="").values_list("name", "species_id"):
        names[name.upper()].add(species_id)
    sides = defaultdict(lambda: ([], []))
    for reaction_id, species_id, coeff in models.Stoichiometry.objects.filter(
            reaction_id__in={link.kinetics.reaction_id for link in links}).values_list("reaction_id", "species_id", "coeff"):
        sides[reaction_id][0 if coeff < 0 else 1].extend([species_id] * max(1, round(abs(coeff))))
    stored_efficiencies = defaultdict(dict)
    for kinetics_id, species_id, value in models.Efficiency.objects.filter(
            kinetics_id__in={link.kinetics_id for link in links}).values_list("kinetics_id", "species_id", "efficiency"):
        stored_efficiencies[kinetics_id][species_id] = value
    by_species = defaultdict(list)
    for link in links:
        left, right = sides[link.kinetics.reaction_id]
        by_species[(tuple(sorted(left)), tuple(sorted(right)))].append(link)
    names_of = defaultdict(set)
    for name, ids in names.items():
        for species_id in ids:
            names_of[species_id].add(name)

    library = os.path.join(model_dir, "RMG-Py-kinetics-library", "reactions.py")
    ea_to_j, molecules = chemkin_lines.units(path, library if os.path.exists(library) else None)
    units = chemkin_lines.rmg_units(ea_to_j, molecules)
    tokens = set(names) | chemkin_lines.species_names(path)
    species = {name: Species(label=name, molecule=[Molecule()]) for name in tokens}
    taken = set()
    new = {}                                     # link id -> (raw_data, base)
    for line in chemkin_lines.read_reactions(path, tokens, ea_to_j):
        if not all(names.get(n.upper()) for n in line["reactants"] + line["products"]):
            report["status"]["no_species"] += 1
            continue
        try:
            author, author_base, collider = _author_rate(line, species, units)
        except Exception:
            report["status"]["rmg_cannot_read"] += 1
            continue
        efficiencies = line_efficiencies(line)
        hits = []
        for left in product(*(names[n.upper()] for n in line["reactants"])):
            for right in product(*(names[n.upper()] for n in line["products"])):
                for link in by_species.get((tuple(sorted(left)), tuple(sorted(right))), []):
                    stored_collider = link.kinetics.specific_collider_id
                    if (collider is None) != (stored_collider is None) or (
                            collider is not None and collider not in names_of.get(stored_collider, ())):
                        continue
                    mine = stored_efficiencies.get(link.kinetics_id, {})
                    differ = sum(1 for name, value in efficiencies.items()
                                 if not any(abs(mine.get(s, math.nan) - value) <= 1e-9 for s in names.get(name, ())))
                    for index, term in enumerate(terms(link.kinetics.raw_data)):
                        try:
                            found = list(leaves(author, term))
                        except Mismatch:
                            continue
                        worst = max((rel(x, y) for _, x, y, _ in found), default=0.0)
                        if worst <= MATCH:
                            hits.append(((link.id, index) in taken, differ, worst, link.id, index, link, found))
        if not hits:
            report["status"]["no_stored_rate"] += 1
            continue
        repeat, _, _, _, index, link, found = min(hits, key=lambda hit: hit[:5])
        report["status"]["paired_again" if repeat else "paired"] += 1
        if repeat:
            continue
        taken.add((link.id, index))
        changed = False
        for parameter, a, s, factor in found:
            if is_rounding(a, s, factor):
                report["numbers"][parameter] += 1
                changed = True
            elif rel(a, s) > EXACT:
                report["other"][parameter] += 1
        raw, base = new.get(link.id) or (copy.deepcopy(link.kinetics.raw_data),
                                         {f: getattr(link.kinetics, f) for f in BASE_FIELDS})
        if changed:
            if raw["type"] in ("multi_arrhenius", "multi_pdep_arrhenius"):
                terms(raw)[index] = restored(author, terms(raw)[index])
            else:
                raw = restored(author, raw)
        if author["type"] == "chebyshev":
            for field in ("min_pressure", "max_pressure"):
                if author_base.get(field) is not None and base.get(field) is not None \
                        and is_rounding(author_base[field], base[field], ATM):
                    base[field] = author_base[field]
                    report["numbers"]["PCHEB"] += 1
                    changed = True
                elif author_base.get(field) is not None and base.get(field) is not None \
                        and rel(author_base[field], base[field]) > EXACT:
                    report["other"]["PCHEB"] += 1
            for field in ("min_temp", "max_temp"):
                if author_base.get(field) is not None and base.get(field) is not None \
                        and rel(author_base[field], base[field]) > EXACT:
                    report["other"]["TCHEB"] += 1
        if changed:
            new[link.id] = (raw, base)
    report["links"] = new
    return report


def _identity(raw, base):
    """What makes two links' rates one record: the raw_data and, for a Chebyshev rate, its T and P range
    (kinetic_data.range_identity: PCHEB with the authors' digits is another record than with 6 digits)."""
    return canonical(raw), tuple(range_identity(raw, *(base[f] for f in BASE_FIELDS)).values())


def _same_record(models, kinetics, raw, base):
    """The other record with the identity of this raw_data and range (kinetics_identity), or None."""
    return (models.Kinetics.objects.filter(**kinetics_identity(kinetics, raw_data=raw, **base))
            .exclude(pk=kinetics.pk).order_by("pk").first())


def _new_record(models, kinetics, raw, base):
    """A copy of *kinetics* with this raw_data and base fields, and copies of its efficiencies."""
    from database.scripts.import_rmg_models import index_new_rows
    fields = {f.attname: getattr(kinetics, f.attname) for f in models.Kinetics._meta.concrete_fields
              if f.attname not in ("id", "raw_data", "rate_fingerprint")}
    made = models.Kinetics.objects.create(**{**fields, **base, "raw_data": raw})
    models.Efficiency.objects.bulk_create([
        models.Efficiency(kinetics=made, species_id=e.species_id, efficiency=e.efficiency)
        for e in models.Efficiency.objects.filter(kinetics=kinetics).order_by("id")])
    index_new_rows(models, kinetics=made)
    return made


def apply_changes(changes, models, report):
    """Gives each link of *changes* ({link id: (raw_data, base)}) the record with its numbers."""
    from database.scripts.import_rmg_models import index_new_rows
    by_record = defaultdict(dict)
    for link in models.KineticsComment.objects.filter(pk__in=changes).select_related("kinetics"):
        by_record[link.kinetics_id][link.id] = changes[link.id]
    for kinetics_id in sorted(by_record):
        kinetics = models.Kinetics.objects.get(pk=kinetics_id)
        wanted = by_record[kinetics_id]
        stored_base = {f: getattr(kinetics, f) for f in BASE_FIELDS}
        stored = _identity(kinetics.raw_data, stored_base)
        # Links group by the identity of their rate: the numbers and, for a Chebyshev rate, the range
        # (only a Chebyshev rate's base fields change here: PCHEB).
        groups, staying = {}, []
        for link in models.KineticsComment.objects.filter(kinetics=kinetics).order_by("id"):
            raw, base = wanted.get(link.id, (kinetics.raw_data, stored_base))
            key = _identity(raw, base)
            if key == stored:
                staying.append(link)
            else:
                groups.setdefault(key, {"raw": raw, "base": base, "links": []})["links"].append(link)
        in_place = None
        if groups and not staying:
            # No model keeps the stored numbers: the record takes those of most of its models.
            key, group = max(groups.items(), key=lambda item: (len(item[1]["links"]), -item[1]["links"][0].id))
            if _same_record(models, kinetics, group["raw"], group["base"]) is None:
                in_place = groups.pop(key)
                staying = in_place["links"]
        for group in groups.values():
            target = _same_record(models, kinetics, group["raw"], group["base"])
            if target is None:
                target = _new_record(models, kinetics, group["raw"], group["base"])
                report["records"]["new"] += 1
            else:
                report["records"]["moved_to_existing"] += 1
            ids = [link.id for link in group["links"]]
            models.KineticsComment.objects.filter(pk__in=ids).update(kinetics=target)
            report["links_moved"] += len(ids)
        if not staying:
            kinetics.delete()
            report["records"]["deleted"] += 1
            continue
        if in_place:
            fields = []
            if canonical(in_place["raw"]) != canonical(kinetics.raw_data):
                kinetics.raw_data = in_place["raw"]
                fields.append("raw_data")
                report["records"]["changed_in_place"] += 1
            if any(in_place["base"][f] != stored_base[f] for f in BASE_FIELDS):
                # The PCHEB range every model of the record gives.
                for field in BASE_FIELDS:
                    setattr(kinetics, field, in_place["base"][field])
                fields += BASE_FIELDS
                report["records"]["range_changed"] += 1
            kinetics.save(update_fields=fields)
            index_new_rows(models, kinetics=kinetics)


def restore(model_dirs, models, apply=True):
    """The authors' digits for the links of these models ([(kinetic model, RMG-models folder)]). Links of
    other models keep their numbers. Returns a report: per model (lines, numbers by parameter, links), and
    the record changes. Without *apply*, everything is done and rolled back."""
    report = {"models": [], "numbers": Counter(), "other": Counter(), "links": 0, "links_moved": 0,
              "records": Counter()}
    with transaction.atomic():
        changes = {}
        for kinetic_model, model_dir in model_dirs:
            found = model_changes(kinetic_model, model_dir, models)
            changes.update(found["links"])
            report["numbers"].update(found["numbers"])
            report["other"].update(found["other"])
            report["links"] += len(found["links"])
            report["models"].append({"model": found["model"], "lines": dict(found["status"]),
                                     "numbers": dict(found["numbers"]), "other": dict(found["other"]),
                                     "links": len(found["links"])})
        apply_changes(changes, models, report)
        if not apply:
            transaction.set_rollback(True)
    return report
