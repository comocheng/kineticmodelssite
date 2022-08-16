from dataclasses import field
from uuid import UUID, uuid4

from pydantic import conlist
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class Structure:
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int
    id: UUID = field(default_factory=uuid4, compare=False)


@dataclass(frozen=True)
class Isomer:
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: conlist(Structure, min_items=0, unique_items=True)
    id: UUID = field(default_factory=uuid4, compare=False)


@dataclass(frozen=True)
class Species:
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: conlist(Isomer, min_items=0, unique_items=True)
    id: UUID = field(default_factory=uuid4, compare=False)
