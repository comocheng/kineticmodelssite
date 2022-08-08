from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class Structure:
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int


@dataclass(frozen=True)
class Isomer:
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: FrozenSet[Structure]


@dataclass(frozen=True)
class Species:
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: FrozenSet[Isomer]
