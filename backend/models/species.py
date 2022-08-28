from pydantic import Field, validator

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
    structures: list[Structure] = Field(min_items=1)


class Species(Model):
    """A generalized chemical species consisting of a unique subset of isomers
    with the same chemical formula
    """

    isomers: list[Isomer] = Field(min_items=1)
    cas_number: str
    prime_id: str | None = None

    @validator("isomers")
    def check_isomers_same_formula(cls, isomers: list[Isomer]):
        assert len(set(i.formula for i in isomers)) <= 1, "Isomers found with different formulas"
        return isomers

    @validator("isomers")
    def check_isomers_different_inchis(cls, isomers: list[Isomer]):
        assert len(set(i.inchi for i in isomers)) == len(isomers), "Duplicate isomers found"
        return isomers
