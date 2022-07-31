from typing import FrozenSet

from backend.models.utils import frozen_dataclass


@frozen_dataclass
class Structure:
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int


@frozen_dataclass
class Isomer:
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: FrozenSet[Structure]


@frozen_dataclass
class Species:
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: FrozenSet[Isomer]
