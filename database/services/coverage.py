"""How much of a model's own CHEMKIN file the Prometheus downloads have, line by line.

The model's own file is the CHEMKIN file RMG-models converted: the --reactions file of the model's
import.sh in its RMG-models folder (settings.RMG_MODELS_PATH). Each reaction line of that file gets
one status:

  in_download        a kinetics link of the model has the line's reaction, and the downloads write it
  fractional         a coefficient is not a whole number (0.35C3H6). RMG-Py's CHEMKIN reader does not
                     read such a line ("fractional stoichiometry, which RMG cannot handle"), so
                     RMG-models and Prometheus do not have it.
  not_identified     a species of the line is not a species of the model in Prometheus: RMG-models
                     did not identify it (the line is in its unidentified_reactions.txt)
  not_in_prometheus  every species is in Prometheus, but no link of the model has the reaction
  no_thermo          the downloads leave the link out: a species has no thermo in Prometheus
  falloff_same_side  the downloads leave the link out: a fall-off reaction with one species record
                     on both sides
  unbalanced         the downloads leave the link out: RMG-Py finds it unbalanced (only an export
                     finds this; the model page does not)

A line and a link are the same reaction when they have the same species on the two sides, in either
direction. Colliders and rates are not compared: a line whose reaction Prometheus has with another
collider, or in a merged rate, counts as in the downloads.
"""
import os
import re
from collections import Counter, defaultdict

from django.conf import settings
from django.core.cache import cache

from database.scripts import chemkin_lines

STATUSES = ("in_download", "fractional", "not_identified", "not_in_prometheus", "no_thermo",
            "falloff_same_side", "unbalanced")
# What each status means, for the download header and the model page.
REASONS = {
    "fractional": "a coefficient that is not a whole number (RMG-Py cannot read these lines)",
    "not_identified": "a species that Prometheus does not have (RMG-models did not identify it)",
    "not_in_prometheus": "a reaction that the model's Prometheus record does not have",
    "no_thermo": "a species that has no thermo in Prometheus",
    "falloff_same_side": "one Prometheus species on both sides of a fall-off reaction",
    "unbalanced": "a reaction that RMG-Py finds unbalanced",
}
_COEFFICIENT = re.compile(r"^(\d*\.\d+|\d+\.)(.+)$")
_FALLOFF_TYPES = ("troe", "lindemann")


def chemkin_path(kinetic_model):
    """The model's own CHEMKIN reactions file in RMG-models, or None."""
    root = getattr(settings, "RMG_MODELS_PATH", None)
    if not root or not kinetic_model.model_name:
        return None
    folder = os.path.join(root, kinetic_model.model_name)
    return chemkin_lines.reactions_file(folder) if os.path.isdir(folder) else None


def _equation(line):
    """The equation of a reaction line: its text without the comment and the three rate numbers."""
    return "".join(line["text"].split("!", 1)[0].split()[:-3])


def _species(line, names):
    """(the line's species names on each side, upper case, without coefficients; whether a
    coefficient is not a whole number). 2OH gives OH twice, as chemkin_lines.split_side does."""
    equation = chemkin_lines.COLLIDER.sub("", _equation(line))
    arrow = "<=>" if "<=>" in equation else ("=>" if "=>" in equation else "=")
    fractional = False
    sides = []
    for side in equation.split(arrow, 1):
        found = []
        for token in chemkin_lines.split_side(side, names):
            upper = token.upper()
            match = None if upper in names else _COEFFICIENT.match(upper)
            if match:
                fractional = True
                upper = match.group(2)
            found.append(upper)
        sides.append(found)
    return sides, fractional


def _link_keys(kinetic_model):
    """{reaction key: [kinetics ids]} for the model's links. The key is the two sides as sorted
    tuples of species ids, in either order."""
    from database.models import KineticsComment, Stoichiometry

    links = list(KineticsComment.objects.filter(kinetic_model=kinetic_model)
                 .values_list("kinetics_id", "kinetics__reaction_id"))
    sides = defaultdict(lambda: ([], []))
    for reaction_id, species_id, coeff in Stoichiometry.objects.filter(
            reaction_id__in={reaction for _, reaction in links}).values_list("reaction_id", "species_id", "coeff"):
        side = sides[reaction_id][0 if coeff < 0 else 1]
        side.extend([species_id] * max(1, int(round(abs(coeff)))))
    keys = defaultdict(list)
    for kinetics_id, reaction_id in links:
        reactants, products = sides[reaction_id]
        keys[_key(reactants, products)].append(kinetics_id)
    return keys


def _key(reactants, products):
    return tuple(sorted((tuple(sorted(reactants)), tuple(sorted(products)))))


def export_left_out(kinetic_model):
    """{kinetics id: reason} of the links the downloads leave out, found by queries as
    exports._build_rmg_reactions decides: a species (or the specific collider) with no thermo at
    all (the export takes another model's thermo when the model has none), and a fall-off reaction
    with one species record on both sides. Unbalanced links need RMG-Py and are not found here."""
    from database.models import KineticsComment, Stoichiometry, Thermo

    rows = list(KineticsComment.objects.filter(kinetic_model=kinetic_model).values_list(
        "kinetics_id", "kinetics__reaction_id", "kinetics__specific_collider_id", "kinetics__raw_data"))
    stoichiometry = defaultdict(list)
    for reaction_id, species_id, coeff in Stoichiometry.objects.filter(
            reaction_id__in={row[1] for row in rows}).values_list("reaction_id", "species_id", "coeff"):
        stoichiometry[reaction_id].append((species_id, coeff))
    species = {s for entries in stoichiometry.values() for s, _ in entries}
    species.update(row[2] for row in rows if row[2])
    with_thermo = set(Thermo.objects.filter(species_id__in=species).values_list("species_id", flat=True))
    left_out = {}
    for kinetics_id, reaction_id, collider_id, raw_data in rows:
        entries = stoichiometry[reaction_id]
        needed = {s for s, _ in entries} | ({collider_id} if collider_id else set())
        reactants = Counter({s: -c for s, c in entries if c < 0})
        products = Counter({s: c for s, c in entries if c > 0})
        kind = (raw_data or {}).get("type") if isinstance(raw_data, dict) else None
        if kind in _FALLOFF_TYPES and reactants and reactants == products:
            left_out[kinetics_id] = "falloff_same_side"
        elif needed - with_thermo:
            left_out[kinetics_id] = "no_thermo"
    return left_out


def line_coverage(kinetic_model, left_out=None):
    """Each reaction line of the model's own CHEMKIN file with its status, or None when the model
    has no such file. `left_out` ({kinetics id: reason}) is what an export left out; without it,
    export_left_out() gives it.

    Returns {"file": path relative to RMG-models, "lines": [{"line", "text", "status",
    "species_not_in_prometheus"}, ...], "counts": {status: lines}}."""
    from database.models import SpeciesName

    path = chemkin_path(kinetic_model)
    if not path:
        return None
    names = chemkin_lines.species_names(path)
    ea_to_j, _ = chemkin_lines.units(path)
    lines = chemkin_lines.read_reactions(path, names, ea_to_j)
    model_species = {name.upper(): species_id for name, species_id in
                     SpeciesName.objects.filter(kinetic_model=kinetic_model).values_list("name", "species_id")}
    keys = _link_keys(kinetic_model)
    if left_out is None:
        left_out = export_left_out(kinetic_model)

    out = []
    for line in lines:
        (reactants, products), fractional = _species(line, names)
        missing = sorted({name for name in reactants + products if name not in model_species})
        if fractional:
            status = "fractional"
        elif missing:
            status = "not_identified"
        else:
            kinetics_ids = keys.get(_key([model_species[n] for n in reactants], [model_species[n] for n in products]))
            if not kinetics_ids:
                status = "not_in_prometheus"
            elif all(k in left_out for k in kinetics_ids):
                status = left_out[kinetics_ids[0]]
            else:
                status = "in_download"
        out.append({"line": line["line"], "text": line["text"], "status": status,
                    "species_not_in_prometheus": missing})
    root = getattr(settings, "RMG_MODELS_PATH", "") or ""
    return {"file": os.path.relpath(path, root) if root else path, "lines": out,
            "counts": dict(Counter(line["status"] for line in out))}


def summary(coverage):
    """The counts of a line_coverage() result, for the model page and the API."""
    if coverage is None:
        return None
    counts = coverage["counts"]
    total = sum(counts.values())
    return {"file": coverage["file"], "lines": total, "in_download": counts.get("in_download", 0),
            "left_out": {status: counts[status] for status in STATUSES[1:] if counts.get(status)},
            "complete": counts.get("in_download", 0) == total}


def cached_summary(kinetic_model):
    """summary(line_coverage(kinetic_model)), kept in the cache until the file, the model's links
    or the thermo records change."""
    from database.models import KineticsComment, Thermo

    path = chemkin_path(kinetic_model)
    if not path:
        return None
    stat = os.stat(path)
    links = KineticsComment.objects.filter(kinetic_model=kinetic_model)
    key = "coverage:{}:{}:{}:{}:{}:{}".format(
        kinetic_model.pk, int(stat.st_mtime), stat.st_size, links.count(),
        links.order_by("-id").values_list("id", flat=True).first(), Thermo.objects.count())
    value = cache.get(key)
    if value is None:
        value = summary(line_coverage(kinetic_model))
        cache.set(key, value, 24 * 3600)
    return value


def _ranges(numbers, positions):
    """'1281-1288, 1325' for the CHEMKIN line numbers, joining lines that are next to each other
    among the file's reaction lines (positions: line number -> index among them)."""
    runs, start, last = [], None, None
    for number in numbers:
        if start is not None and positions[number] == positions[last] + 1:
            last = number
            continue
        if start is not None:
            runs.append(f"{start}-{last}" if last != start else str(start))
        start = last = number
    if start is not None:
        runs.append(f"{start}-{last}" if last != start else str(start))
    return runs


def header_lines(kinetic_model, coverage, width=96):
    """CHEMKIN comment lines for the top of a generated download: how many of the model's own lines
    it has, and the line numbers of the others, by reason."""
    if coverage is None:
        return []
    counts = coverage["counts"]
    total = sum(counts.values())
    have = counts.get("in_download", 0)
    if have == total:
        return [f"! This file has all {total:,} reaction lines of the model's own CHEMKIN file",
                f"! ({coverage['file']} in RMG-models)."]
    lines = [f"! This file has {have:,} of the {total:,} reaction lines of the model's own CHEMKIN file",
             f"! ({coverage['file']} in RMG-models). The 'original mechanism' download has the model's",
             "! own files. This file does not have these lines (line numbers in that file):"]
    positions = {line["line"]: index for index, line in enumerate(coverage["lines"])}
    for status in STATUSES[1:]:
        numbers = [line["line"] for line in coverage["lines"] if line["status"] == status]
        if not numbers:
            continue
        lines.append(f"!   {len(numbers):,} with {REASONS[status]}:")
        current = "!     "
        for run in _ranges(numbers, positions):
            piece = run if current.endswith("     ") else f", {run}"
            if len(current) + len(piece) > width:
                lines.append(current + ",")
                current, piece = "!     ", run
            current += piece
        lines.append(current)
    return lines
