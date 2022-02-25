from pydantic import BaseModel
from typing import List


class Author(BaseModel):
    firstname: str
    lastname: str


class Source(BaseModel):
    doi: str
    prime_id: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: List[Author]


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


class ReactionSpecies(BaseModel):
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


class Reaction(BaseModel):
    prime_id: str
    reaction_species: List[ReactionSpecies]
    reversible: bool


class Arrhenius(BaseModel):
    a: float
    a_si: float
    a_delta: float | None
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: float | None
    e_units: str


class ArrheniusEP(BaseModel):
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str


class ColliderSpecies(BaseModel):
    species: Species
    efficiency: float


class Kinetics(BaseModel):
    prime_id: str
    reaction: Reaction
    data: Arrhenius | ArrheniusEP
    for_reverse: bool
    uncertainty: float
    min_temp: float
    max_temp: float
    min_pressure: float
    max_pressure: float
    collider_species: List[ColliderSpecies]
    # source: Source


class NamedSpecies(BaseModel):
    name: str
    species: Species


class Thermo(BaseModel):
    prime_id: str
    preferred_key: str
    species: Species
    reference_temp: float
    reference_pressure: float
    enthalpy_formation: float
    polynomial1: List[float]
    polynomial2: List[float]
    min_temp1: float
    max_temp1: float
    min_temp2: float
    max_temp2: float
    source: Source


class Transport(BaseModel):
    prime_id: str
    species: Species
    geometry: float
    well_depth: float
    collision_diameter: float
    dipole_moment: float
    polarizability: float
    rotational_relaxation: float
    source: Source

class KineticModel(BaseModel):
    name: str
    prime_id: str
    named_species: List[NamedSpecies]
    kinetics: List[Kinetics]
    thermo: List[Thermo]
    transport: List[Transport]
    source: Source
