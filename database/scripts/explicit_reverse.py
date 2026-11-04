"""The model's own reverse rates: REV / A n Ea / on a reversible line of its CHEMKIN file.

RMG-Py's CHEMKIN reader drops a non-zero REV ("Ignoring explicit reverse rate", rmgpy/chemkin.pyx) and keeps
the reaction reversible with the forward rate only, so RMG-models has only the forward rate. Without the
REV, kms and its downloads gave the reverse rate from thermochemistry, which is not the model's: of the
31,997 REV lines of 46 models, 14% are more than 10x off at 1000 K (cleanup_evidence/explicit_reverse_rates).
The REV belongs to the model, not to the rate record: models that share a rate write other REVs or none.
So the model's link keeps it, as KineticsComment.reverse_rate:

    {"terms": [{"line": 15766, "text": "rev / 8.926E+03 2.70 1.055E+04 /", "arrhenius": {Arrhenius raw_data}}]}

one item per rate term of the link: a multi_arrhenius has one term per DUPLICATE line, each with its own
REV or none (null). The A is per mole, in cm, for the reverse reaction's order.

A REV line goes to the model's link whose reaction has the line's species in the line's direction (the
model's SpeciesName rows) and whose rate term has the line's forward A, n and Ea. RMG-models is only read.
"""
import itertools
import logging
import math
import os
import re
from collections import Counter, defaultdict

from django.db import transaction
from rmgpy.quantity import ScalarQuantity

from database.models import kinetic_data as kd
from database.scripts import chemkin_lines

logger = logging.getLogger(__name__)

REV = re.compile(r"(?i)(?<![A-Z0-9])REV\s*/\s*(\S+)\s+(\S+)\s+(\S+?)\s*/")
FALLOFF = {"LOW", "HIGH", "TROE", "SRI"}
COLLIDER = re.compile(r"\(\s*\+\s*([^)]+?)\s*\)")
# Ea unit of the CHEMKIN file (J/mol per unit, chemkin_lines.units) -> the unit kept; others go to J/mol.
EA_UNITS = {4.184: "cal/mol", 4184.0: "kcal/mol", 1.0: "J/mol", 1000.0: "kJ/mol"}
A_UNITS = {1: "s^-1", 2: "cm^3/(mol*s)", 3: "cm^6/(mol^2*s)"}


def _number(text):
    return float(text.replace("D", "E").replace("d", "e"))


def rev_lines(path, names, ea_to_j, molecules=False):
    """The reversible lines of a CHEMKIN file with a non-zero REV: the line of chemkin_lines.read_reactions
    with "rev" (A, n and Ea as written), "rev_text", "duplicate", "falloff" and "collider" (the name in
    (+X), "M" for (+M) or + M, None)."""
    with open(path, errors="replace") as handle:
        text = handle.read().splitlines()
    found = []
    for line in chemkin_lines.read_reactions(path, names, ea_to_j):
        if not line["reversible"]:
            continue
        aux = []
        for raw in text[line["line"]:]:
            body = raw.split("!", 1)[0].strip()
            # Auxiliary lines have no "="; the next reaction line or END ends them.
            if "=" in body or body.upper().startswith("END"):
                break
            if body:
                aux.append(body)
        rev = next((m for m in (REV.search(body) for body in aux) if m), None)
        if rev is None:
            continue
        try:
            a, n, e = (_number(x) for x in rev.groups())
        except ValueError:
            logger.warning(f"{path} line {line['line']}: cannot read {rev.group(0)}")
            continue
        if a == 0:
            continue                     # REV / 0 0 0 /: irreversible, as RMG-models has it
        words = {w.upper() for body in aux for w in re.findall(r"[A-Za-z]+(?=\s*/|\s*$)", body)}
        equation = line["text"].split("!", 1)[0]
        collider = COLLIDER.search(equation)
        found.append({**line, "rev": (a, n, e), "rev_text": rev.group(0).strip(),
                      "duplicate": any(w.startswith("DUP") for w in words),
                      "falloff": bool(words & FALLOFF),
                      "collider": (collider.group(1).upper() if collider else "M" if line["third_body"] else None)})
    return found


def reverse_arrhenius(line, ea_to_j, molecules=False):
    """The line's REV as Arrhenius raw_data, per mole and in cm; None if its order has no unit."""
    a, n, e = line["rev"]
    order = len(line["products"]) + (1 if line["third_body"] and not line["falloff"] else 0)
    if order not in A_UNITS:
        return None
    if molecules:
        a *= chemkin_lines.AVOGADRO ** (order - 1)
    e_si = e * ea_to_j
    e, e_units = (e, EA_UNITS[ea_to_j]) if ea_to_j in EA_UNITS else (e_si, "J/mol")   # K, eV: J/mol
    return kd.Arrhenius(type="arrhenius", a=a, a_si=ScalarQuantity(a, A_UNITS[order]).value_si,
                        a_units=A_UNITS[order], n=n, e=e, e_si=e_si, e_units=e_units).dict()


def forward_terms(raw_data):
    """(A as stored, n, Ea in J/mol) of each rate term, as a CHEMKIN line writes it: the high-pressure
    rate of a fall-off, the low one of a three-body rate; None for a term a line cannot be compared with."""
    kind = raw_data.get("type")
    if kind == "arrhenius":
        terms = [raw_data]
    elif kind == "multi_arrhenius":
        terms = raw_data["arrhenius_set"]
    elif kind in ("troe", "lindemann"):
        terms = [raw_data["high_arrhenius"]]
    elif kind == "third_body":
        terms = [raw_data["low_arrhenius"]]
    else:
        return [None]
    return [(t["a"], t["n"], t["e_si"]) for t in terms]


def has_reverse_field(models):
    return any(f.name == "reverse_rate" for f in models.KineticsComment._meta.get_fields())


def attach(kinetic_model, model_dir, models, apply=True):
    """Set reverse_rate on each of the model's links from its CHEMKIN file, and clear it where no REV line
    gives one. Returns a report: counts and one row per REV line (status matched, no_species,
    no_link, irreversible_link, ambiguous or no_unit)."""
    report = {"model": kinetic_model.model_name, "rev_lines": 0, "set": 0, "cleared": 0, "unchanged": 0,
              "status": Counter(), "lines": []}
    path = chemkin_lines.reactions_file(model_dir) if model_dir and os.path.isdir(model_dir) else None
    links = list(models.KineticsComment.objects.filter(kinetic_model=kinetic_model)
                 .select_related("kinetics").order_by("id"))
    lines, ea_to_j, molecules = [], 4.184, False
    names = defaultdict(set)              # upper-case name -> the model's species records
    for name, species_id in models.SpeciesName.objects.filter(kinetic_model=kinetic_model) \
            .values_list("name", "species_id"):
        names[name.upper()].add(species_id)
    if path:
        tokens = set(names) | chemkin_lines_species(path)
        library = os.path.join(model_dir, "RMG-Py-kinetics-library", "reactions.py")
        ea_to_j, molecules = chemkin_lines.units(path, library if os.path.exists(library) else None)
        lines = rev_lines(path, tokens, ea_to_j, molecules)
    report["rev_lines"] = len(lines)

    sides = defaultdict(lambda: ([], []))
    for reaction_id, species_id, coeff in models.Stoichiometry.objects.filter(
            reaction_id__in={link.kinetics.reaction_id for link in links}).values_list("reaction_id", "species_id", "coeff"):
        side = sides[reaction_id][0 if coeff < 0 else 1]
        side.extend([species_id] * max(1, round(abs(coeff))))
    by_species = defaultdict(list)
    for link in links:
        left, right = sides[link.kinetics.reaction_id]
        by_species[(tuple(sorted(left)), tuple(sorted(right)))].append(link)
    collider_names = defaultdict(set)     # species record -> its upper-case names
    for name, ids in names.items():
        for species_id in ids:
            collider_names[species_id].add(name)

    wanted, taken = defaultdict(dict), set()
    for line in lines:
        row = {"model": kinetic_model.model_name, "line": line["line"], "text": line["text"],
               "rev": line["rev_text"], "kinetics_id": "", "term": ""}
        report["lines"].append(row)
        ids = [names.get(n.upper()) for n in line["reactants"] + line["products"]]
        if not all(ids):
            row["status"] = "no_species"
            continue
        # Each name is one record of the model; a name of two records (rare) tries each.
        keys = {(tuple(sorted(a)), tuple(sorted(b))) for a, b in _choices(
            [names[n.upper()] for n in line["reactants"]], [names[n.upper()] for n in line["products"]])}
        hits = []
        for key in keys:
            for link in by_species.get(key, []):
                for term, rate in enumerate(forward_terms(link.kinetics.raw_data)):
                    if (link.id, term) not in taken and rate is not None and chemkin_lines.same_rate(
                            rate, (line["A"], line["n"], line["Ea"]), molecules):
                        hits.append((link, term))
        if len({link.id for link, _ in hits}) > 1:
            # (+AR) and (+M) rates of one reaction: the line's collider decides.
            hits = [(link, term) for link, term in hits if _collider(link, collider_names) == line["collider"]] or hits
        if not hits:
            row["status"] = "no_link"
            continue
        if len({link.id for link, _ in hits}) > 1:
            row["status"] = "ambiguous"
            row["kinetics_id"] = " ".join(sorted({str(link.kinetics_id) for link, _ in hits}))
            continue
        # DUPLICATE lines with one rate: the terms of a multi-rate are in the order of the lines.
        link, term = min(hits, key=lambda hit: hit[1])
        row["kinetics_id"], row["term"] = link.kinetics_id, term
        if not link.reversible:
            row["status"] = "irreversible_link"
            continue
        arrhenius = reverse_arrhenius(line, ea_to_j, molecules)
        if arrhenius is None:
            row["status"] = "no_unit"
            continue
        taken.add((link.id, term))
        wanted[link.id][term] = {"line": line["line"], "text": line["rev_text"], "arrhenius": arrhenius}
        row["status"] = "matched"
    report["status"] = Counter(row["status"] for row in report["lines"])

    changed = []
    for link in links:
        terms = wanted.get(link.id)
        value = ({"terms": [terms.get(i) for i in range(len(forward_terms(link.kinetics.raw_data)))]}
                 if terms else None)
        if _same(value, link.reverse_rate):
            report["unchanged"] += value is not None
            continue
        report["set" if value is not None else "cleared"] += 1
        link.reverse_rate = value
        changed.append(link)
    if apply and changed:
        with transaction.atomic():
            models.KineticsComment.objects.bulk_update(changed, ["reverse_rate"], batch_size=500)
    return report


def _same(a, b):
    """Whether two stored values are one. PostgreSQL keeps 1.233e66 as an integer, so numbers are
    compared as floats."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=0.0)
    return a == b


def chemkin_lines_species(path):
    """The upper-case names of the file's SPECIES block."""
    with open(path, errors="replace") as handle:
        block = re.search(r"^\s*SPEC\w*(.*?)^\s*END", handle.read(), re.S | re.M | re.I)
    return {t.upper() for line in block.group(1).splitlines() for t in line.split("!")[0].split()} if block else set()


def _choices(left, right):
    """Every (reactant records, product records) when a name has more than one record."""
    for a in itertools.product(*left):
        for b in itertools.product(*right):
            yield a, b


def _collider(link, collider_names):
    """The link's collider as rev_lines gives a line's: the name of its specific collider, "M" for a
    third-body or fall-off rate, None."""
    if link.kinetics.specific_collider_id:
        names = collider_names.get(link.kinetics.specific_collider_id) or {None}
        return sorted(names)[0]
    return "M" if link.kinetics.raw_data.get("type") in ("third_body", "troe", "lindemann") else None
