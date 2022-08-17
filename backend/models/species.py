from dataclasses import Field
from uuid import UUID, uuid4

from pydantic import confrozenset
from pydantic.dataclasses import dataclass

from backend.models.model import Model


class Structure(Model):
    """An unambiguous representation of an atom or molecule"""

    adjlist: str
    smiles: str
    multiplicity: int



class Isomer(Model):
    """A molecule with a particular bonding structure"""

    formula: str
    inchi: str
    structures: confrozenset(Structure, min_items=0)



class Species(Model):
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    prime_id: str
    cas_number: str
    isomers: confrozenset(Isomer, min_items=0)
