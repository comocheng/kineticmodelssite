"""The model's own CHEMKIN reaction lines, read beside its RMG-Py libraries.

RMG-models converted each model from its CHEMKIN file (the --reactions file of the model's import.sh)
and keeps that file in the model folder. Where two of the model's names had one SMILES, the
converter took them for one species and wrote both names' reactions as one library entry: a
MultiArrhenius with one term per CHEMKIN line. The lines say which name each rate belongs to.
"""
import math
import os
import re
from collections import Counter

# J/mol per unit of Ea named on the REACTIONS line, and per unit RMG-models wrote into a library.
EA_TO_J = {"CAL/MOLE": 4.184, "KCAL/MOLE": 4184.0, "JOULES/MOLE": 1.0, "KJOULES/MOLE": 1000.0,
           "KELVINS": 8.314462618, "EVOLTS": 96485.33212}
LIBRARY_EA_TO_J = {"cal/mol": 4.184, "kcal/mol": 4184.0, "J/mol": 1.0, "kJ/mol": 1000.0}
AVOGADRO = 6.02214076e23

AUX = {"LOW", "TROE", "SRI", "PLOG", "REV", "DUPLICATE", "DUP", "FORD", "RORD", "LT", "RLT", "HIGH",
       "CHEB", "TCHEB", "PCHEB", "UNITS", "XSMI", "MOME", "TDEP", "EXCI", "JAN", "FIT1", "USRPROG", "END",
       "REACTIONS", "REAC"}
COLLIDER = re.compile(r"\(\s*\+\s*[^)]+\)")
NUMBER = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eEdD][-+]?\d+)?$")
PLOG = re.compile(r"\s*PLOG\s*/\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*/", re.I)


def reactions_file(model_dir):
    """The CHEMKIN file the model was converted from, or None."""
    script = os.path.join(model_dir, "import.sh")
    if not os.path.exists(script):
        return None
    with open(script, errors="replace") as handle:
        match = re.search(r"--reactions\s+(\S+)", handle.read())
    path = os.path.join(model_dir, match.group(1)) if match else None
    return path if path and os.path.exists(path) else None


def units(path, library_path=None):
    """(J/mol per Ea unit, whether A is per molecule) of a CHEMKIN file. A file whose REACTIONS line
    names no unit (MatheuCH4, in kcal/mol) takes the unit RMG-models wrote into its library."""
    molecules = False
    with open(path, errors="replace") as handle:
        for raw in handle:
            body = raw.split("!", 1)[0].upper().split()
            if body and body[0].startswith("REAC"):
                molecules = "MOLECULES" in body[1:]
                for token in body[1:]:
                    if token in EA_TO_J:
                        return EA_TO_J[token], molecules
                break
    if library_path and os.path.exists(library_path):
        with open(library_path, errors="replace") as handle:
            written = Counter(re.findall(r"Ea=\(\s*[-+0-9.eE]+\s*,\s*'([^']+)'\)", handle.read()))
        if written and written.most_common(1)[0][0] in LIBRARY_EA_TO_J:
            return LIBRARY_EA_TO_J[written.most_common(1)[0][0]], molecules
    return EA_TO_J["CAL/MOLE"], molecules


def split_side(side, names):
    """The species of one side of a CHEMKIN equation (names may contain '+'; 2OH is OH twice).
    `names` holds the model's names in upper case."""
    tokens = COLLIDER.sub("", side).replace(" ", "").split("+")
    out, i = [], 0
    while i < len(tokens):
        for j in range(len(tokens), i, -1):
            candidate = "+".join(tokens[i:j])
            if candidate.upper() in names or candidate.upper() == "M":
                out.append(candidate)
                i = j
                break
            counted = re.match(r"^(\d+)(.+)$", candidate)
            if counted and counted.group(2).upper() in names:
                out.extend([counted.group(2)] * int(counted.group(1)))
                i = j
                break
        else:
            out.append(tokens[i])
            i += 1
    return [t for t in out if t and t.upper() != "M"]


def read_reactions(path, names, ea_to_j):
    """The reaction lines of a CHEMKIN file: line number, text, reactants, products, reversible,
    third_body, A, n, Ea (J/mol) and the first PLOG rate (A, n, Ea in J/mol) when there is one."""
    reactions, last, inside = [], None, False
    with open(path, errors="replace") as handle:
        lines = handle.read().splitlines()
    for number, raw in enumerate(lines, 1):
        body = raw.split("!", 1)[0].strip()
        first = body.split("/")[0].split()
        head = first[0].upper() if first else ("AUX" if body else "")
        if head.startswith("REAC"):
            inside = True
            continue
        if not inside or not body:
            continue
        if head == "END":
            inside = False
            continue
        if head in AUX or head == "AUX" or "=" not in body:
            plog = PLOG.match(body)
            if last is not None and plog and last["plog"] is None:
                a, n, e = (float(x.replace("D", "E").replace("d", "e")) for x in plog.groups()[1:])
                last["plog"] = (a, n, e * ea_to_j)
            continue
        parts = body.split()
        numbers = []
        while parts and NUMBER.match(parts[-1]) and len(numbers) < 3:
            numbers.insert(0, float(parts.pop().replace("d", "e").replace("D", "e")))
        if len(numbers) != 3:
            continue
        equation = "".join(parts)
        arrow = "<=>" if "<=>" in equation else ("=>" if "=>" in equation else "=")
        left, right = equation.split(arrow, 1)
        tokens = COLLIDER.sub("", left).split("+") + COLLIDER.sub("", right).split("+")
        last = {"line": number, "text": raw.strip(), "reactants": split_side(left, names),
                "products": split_side(right, names), "reversible": arrow != "=>",
                "third_body": bool(COLLIDER.search(equation)) or any(t.upper() == "M" for t in tokens),
                "A": numbers[0], "n": numbers[1], "Ea": numbers[2] * ea_to_j, "plog": None}
        reactions.append(last)
    return reactions


def same_rate(a, b, molecules=False):
    """Whether two (A, n, Ea in J/mol) rates are one: A may differ by powers of Avogadro's number
    when the file gives A per molecule."""
    (a1, n1, e1), (a2, n2, e2) = a, b
    if abs(n1 - n2) > 1e-6 or abs(e1 - e2) > max(0.2, 1e-4 * abs(e1)):
        return False
    if a1 == a2 == 0:
        return True
    if a1 == 0 or a2 == 0:
        return False
    ratio = math.log10(abs(a1 / a2))
    powers = (0, 1, 2, -1, -2) if molecules else (0,)
    return any(abs(ratio - k * math.log10(AVOGADRO)) < 1e-3 for k in powers)
