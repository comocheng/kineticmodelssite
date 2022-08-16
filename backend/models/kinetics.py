from dataclasses import field
from typing import Union
from uuid import UUID, uuid4

from pydantic import conlist
from pydantic.dataclasses import dataclass

from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Species


@dataclass(frozen=True)
class Arrhenius:
    a: float
    a_si: float
    a_delta: float | None
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: float | None
    e_units: str
    s: str


@dataclass(frozen=True)
class ArrheniusEP:
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str


@dataclass(frozen=True)
class ColliderSpecies:
    species: Species
    efficiency: float


@dataclass(frozen=True)
class Kinetics:
    prime_id: str
    reaction: Reaction
    data: Union[Arrhenius, ArrheniusEP]
    for_reverse: bool
    uncertainty: float
    min_temp: float
    max_temp: float
    min_pressure: float
    max_pressure: float
    collider_species: conlist(ColliderSpecies, unique_items=True)
    source: Source
    id: UUID = field(default_factory=uuid4, compare=False)
