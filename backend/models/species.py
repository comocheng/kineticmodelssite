from typing import FrozenSet

from backend.models.utils import Model


class Structure(Model):
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int


class Isomer(Model):
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: FrozenSet[Structure]


class Species(Model):
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: FrozenSet[Isomer]
