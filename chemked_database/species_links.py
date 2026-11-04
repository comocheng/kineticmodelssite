"""The species record of a ChemKED mixture component, found from the component's InChI.

ChemKED gives a component's standard InChI, which CompositionSpecies stores without the
``InChI=`` prefix (``1S/O2/c1-2``). The species records keep RMG's augmented InChI, with the
unpaired electrons (/u) and lone pairs (/lp) as extra layers: triplet O2 is
``InChI=1S/O2/c1-2/u1,2``, and the plain ``InChI=1S/O2/c1-2`` is the record of singlet O2. So the
records are compared by standard InChI. A standard InChI has no spin: when records of several
spins share it, the component is the ground state, from GROUND_STATES. An excited-state record
(OH*) is never the species of a component, because an InChI denotes the ground state.
"""

import re

from database.models import Species, Structure

try:
    from rdkit import Chem
    from rdkit import RDLogger

    RDLogger.DisableLog("rdApp.*")
except ImportError:  # pragma: no cover
    Chem = None

# RMG writes the unpaired electrons (/u) and lone pairs (/lp) of a structure as extra layers.
RMG_LAYERS = re.compile(r"/(?:u|lp)[^/]*")

# Standard InChI -> multiplicity of the ground state, for the molecules that experiments use and
# whose records of several spins share one standard InChI. A standard InChI that records of
# several spins share and that is not listed here links to no record.
GROUND_STATES = {
    "InChI=1S/O2/c1-2": 3,     # O2 X3Σg-, not singlet O2 (a1Δg)
    "InChI=1S/CO/c1-2": 1,     # CO X1Σ+, not a triplet
    "InChI=1S/N2O/c1-2-3": 1,  # N2O X1Σ+, not a triplet
    "InChI=1S/O": 3,           # O(3P), not O(1D)
}

# Why a component has no species record.
NO_INCHI, NO_RECORD, SEVERAL_SPINS = "no InChI", "no record", "records of several spins"


def standard_inchi(value):
    """The standard InChI of a component's or a record's InChI: with the ``InChI=`` prefix and
    without RMG's /u and /lp layers."""
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("InChI="):
        value = f"InChI={value}"
    return RMG_LAYERS.sub("", value)


def _by_standard_inchi(std):
    """species id -> multiplicities of its structures, for the ground-state records whose
    InChI is this standard InChI, perhaps followed by RMG's layers."""
    found = {}
    rows = (Species.objects.filter(electronic_state="", isomers__inchi__startswith=std)
            .values_list("pk", "isomers__inchi", "isomers__structure__multiplicity"))
    for pk, inchi, multiplicity in rows:
        if standard_inchi(inchi) == std:
            spins = found.setdefault(pk, set())
            if multiplicity is not None:
                spins.add(multiplicity)
    return found


def _by_inchikey(std):
    """The same, matched by standard InChIKey (Structure.structure_key is
    "<InChIKey>-<multiplicity>"), for an InChI written differently from the records'."""
    key = Chem.InchiToInchiKey(std) if Chem is not None else None
    if not key:
        return {}
    found = {}
    rows = (Structure.objects.filter(structure_key__startswith=f"{key}-",
                                     isomer__species__electronic_state="")
            .values_list("isomer__species", "multiplicity"))
    for pk, multiplicity in rows:
        if pk is not None:
            found.setdefault(pk, set()).add(multiplicity)
    return found


class SpeciesLinker:
    """Finds the species record of a component's InChI. It keeps what it found, so one linker
    serves all the components of an import."""

    def __init__(self):
        self._found = {}

    def species_id(self, inchi):
        return self.resolve(inchi)[0]

    def resolve(self, inchi):
        """(species id, how it was found) or (None, why there is none)."""
        std = standard_inchi(inchi)
        if not std:
            return None, NO_INCHI
        if std not in self._found:
            self._found[std] = self._resolve(std)
        return self._found[std]

    @staticmethod
    def _resolve(std):
        candidates, how = _by_standard_inchi(std), "standard InChI"
        if not candidates:
            candidates, how = _by_inchikey(std), "InChIKey"
        if not candidates:
            return None, NO_RECORD
        if len(candidates) == 1:
            return next(iter(candidates)), how
        ground = GROUND_STATES.get(std)
        chosen = [pk for pk, spins in candidates.items() if ground in spins]
        if len(chosen) == 1:
            return chosen[0], "ground state"
        return None, SEVERAL_SPINS
