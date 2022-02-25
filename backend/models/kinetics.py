from typing import List

from pydantic import BaseModel

from .species import Species
from .reaction import Reaction
from .source import Source


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
    source: Source
