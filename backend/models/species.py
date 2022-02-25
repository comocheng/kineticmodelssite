from typing import List

from pydantic import BaseModel


class Structure(BaseModel):
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int


class Isomer(BaseModel):
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: List[Structure]


class Species(BaseModel):
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: List[Isomer]
