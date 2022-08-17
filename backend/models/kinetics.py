from dataclasses import field
from typing import Optional, Union
from uuid import UUID, uuid4

from pydantic.dataclasses import dataclass
from backend.models.model import Model

from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Species


class Arrhenius(Model):
    a: float
    a_si: float
    a_delta: Optional[float]
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: Optional[float]
    e_units: str
    s: str


class ArrheniusEP(Model):
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str


class ColliderSpecies(Model):
    species: Species
    efficiency: float


KineticsData = Union[Arrhenius, ArrheniusEP]


class Kinetics(Model):
    prime_id: str
    reaction: Reaction
    data: KineticsData
    for_reverse: bool
    uncertainty: Optional[float]
    min_temp: Optional[float]
    max_temp: Optional[float]
    min_pressure: Optional[float]
    max_pressure: Optional[float]
    source: Source
