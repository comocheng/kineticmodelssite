"""Local, stereochemistry-preserving identities for search and API validation."""

import re

from rdkit import Chem, rdBase


def canonical_smiles(value):
    if not value or len(value) > 500:
        return None
    # Do not accept a trailing name or CXSMILES metadata as part of a search.
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    with rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(value, params)
    if molecule is None:
        return None
    for atom in molecule.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)


def canonical_inchi(value):
    # Augmented RMG InChIs encode spin/radicals in extra layers. Match those
    # literally rather than silently discarding information through standard InChI.
    if re.search(r"/(u|lp|mult)", value):
        return None
    with rdBase.BlockLogs():
        molecule = Chem.MolFromInchi(value)
    return canonical_smiles(Chem.MolToSmiles(molecule)) if molecule is not None else None


def normalize_formula(value):
    """Recognize a molecular formula and return Hill order (including subscripts)."""
    value = value.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    tokens = re.findall(r"([A-Z][a-z]?)([1-9][0-9]*)?", value)
    if not tokens or "".join(element + number for element, number in tokens) != value:
        return None
    elements = {Chem.GetPeriodicTable().GetElementSymbol(i) for i in range(1, 119)}
    if any(element not in elements for element, _ in tokens):
        return None
    # Repeated elements usually indicate SMILES (CCO), not a molecular formula.
    if len({element for element, _ in tokens}) != len(tokens):
        return None
    counts = {element: int(number or 1) for element, number in tokens}
    order = sorted(counts)
    if "C" in counts:
        order = ["C"] + (["H"] if "H" in counts else [])
        order += sorted(set(counts) - {"C", "H"})
    return "".join(element + (str(counts[element]) if counts[element] != 1 else "")
                   for element in order)


# ---------------------------------------------------------------------------
# Comparison rules shared with RMG-Py's evidence_index.py, which the importer uses to detect
# copied chemistry. Keeping the same keys and tolerances means the site and the importer agree
# on what counts as the same structure, the same rate and the same thermo.

RATE_TEMPERATURES = (500.0, 1000.0, 1500.0)  # K
RATE_PRESSURE = 1e5                          # Pa
RATE_TOLERANCE = 0.01                        # in log10 k, about 2%
THERMO_TEMPERATURES = (300, 400, 500, 600, 800, 1000, 1500, 2000)
COPIED_THERMO_TOLERANCE = 1e-3               # relative: the same polynomial, not merely similar
SIMILAR_THERMO_TOLERANCE = 0.05              # HeatCapacityModel.is_identical_to

NOBLE_GASES = {"He", "Ne", "Ar", "Kr", "Xe"}
HALOGENS = {"F", "Cl", "Br", "I"}


def structure_key(molecule):
    """The same for all resonance forms of a structure, different between spin states:
    the standard InChIKey plus the multiplicity (evidence_index.structure_key)."""
    return f"{molecule.to_inchi_key()}-{molecule.multiplicity}"


def species_key(structure_keys, electronic_state=""):
    """One key per species; a resonance collection's structures normally share one key.

    An excited state (OH*) has its ground state's structures, so its state is appended."""
    key = "|".join(sorted(set(key for key in structure_keys if key)))
    return f"{key}@{electronic_state}" if key and electronic_state else key


def inchikey_of(key):
    """The standard InChIKey in a structure_key ("<InChIKey>-<multiplicity>")."""
    return key.rsplit("-", 1)[0] if key else ""


def inchikey_species_map():
    """Standard InChIKey -> species id, read from Structure.structure_key, which is the
    source of truth for species identifiers. The lowest species id wins a shared key.
    An InChIKey denotes the ground state, so excited-state species are left out."""
    from database.models import Structure

    mapping = {}
    rows = (Structure.objects.exclude(structure_key="").exclude(isomer__species=None)
            .filter(isomer__species__electronic_state="")
            .order_by("isomer__species").values_list("structure_key", "isomer__species"))
    for key, species_id in rows:
        inchikey = inchikey_of(key)
        if inchikey:
            mapping.setdefault(inchikey, species_id)
    return mapping


def reaction_key(reactant_keys, product_keys):
    """A direction-insensitive reaction key and the stored direction relative to it.

    Each side is the sorted multiset of its species keys; the canonical orientation puts the
    smaller side first. Returns (key, +1 or -1), or ("", 0) if any species has no key.
    """
    if not reactant_keys or not product_keys or not all(reactant_keys) or not all(product_keys):
        return "", 0
    left, right = " + ".join(sorted(reactant_keys)), " + ".join(sorted(product_keys))
    if left <= right:
        return f"{left} = {right}", 1
    return f"{right} = {left}", -1


def formula_elements(formula):
    counts = {}
    for element, number in re.findall(r"([A-Z][a-z]?)(\d*)", formula or ""):
        counts[element] = counts.get(element, 0) + int(number or 1)
    return counts


def reaction_layer(formulas):
    """The sub-mechanism layer of a reaction from its non-collider species' formulas:
    H2/O2, C1, C2, C3 or C≥4 by the largest carbon count, tagged +N, +S and +Hal."""
    elements, max_carbon = set(), 0
    for formula in formulas:
        counts = formula_elements(formula)
        elements |= set(counts) - NOBLE_GASES
        max_carbon = max(max_carbon, counts.get("C", 0))
    tags = [tag for tag, present in (("N", "N" in elements), ("S", "S" in elements),
                                     ("Hal", bool(elements & HALOGENS))) if present]
    if max_carbon:
        base = "C≥4" if max_carbon >= 4 else f"C{max_carbon}"
    elif tags:
        return "+".join(tags)
    else:
        base = "H2/O2"
    return "+".join([base, *tags])


# Evans-Polanyi and Blowers-Masel rates take the reaction enthalpy, not pressure, as the second
# argument of get_rate_coefficient; without it they have no single rate.
ENTHALPY_DEPENDENT = {"ArrheniusEP", "ArrheniusBM"}


def rate_fingerprint(rmg_kinetics):
    """log10 k (SI units) at RATE_TEMPERATURES and RATE_PRESSURE, or None if it can't be evaluated (evidence_index.rate_fingerprint)."""
    import math
    if type(rmg_kinetics).__name__ in ENTHALPY_DEPENDENT:
        return None
    values = []
    try:
        for temperature in RATE_TEMPERATURES:
            k = rmg_kinetics.get_rate_coefficient(temperature, RATE_PRESSURE)
            if not (k > 0 and math.isfinite(k)):
                return None
            values.append(round(math.log10(k), 4))
    except Exception:
        return None
    return values


def rates_match(a, b):
    return bool(a and b) and all(abs(x - y) <= RATE_TOLERANCE for x, y in zip(a, b))


def combine_fingerprints(fingerprints):
    """A reaction's total rate when a model gives it as several DUPLICATE expressions:
    log10 of the summed k at each temperature. [] if any part cannot be evaluated."""
    import math
    if len(fingerprints) == 1:
        return fingerprints[0] or []
    if not fingerprints or any(not f for f in fingerprints):
        return []
    return [round(math.log10(sum(10 ** f[i] for f in fingerprints)), 4) for i in range(len(fingerprints[0]))]


THIRD_BODY_TYPES = {"third_body", "troe", "lindemann"}


def rate_class(kinetics_type):
    """'M' for third-body and falloff rates, 'plain' otherwise. Reaction identity leaves out M,
    so A = B and A (+M) = B (+M) share a reaction; they are different rates, never summed."""
    return "M" if kinetics_type in THIRD_BODY_TYPES else "plain"
