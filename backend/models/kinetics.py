from typing import FrozenSet, Union

from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Species
from backend.models.utils import Model


class Arrhenius(Model):
    a: float
    a_si: float
    a_delta: float | None
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: float | None
    e_units: str

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


class Kinetics(Model):
    prime_id: str
    reaction: Reaction
    data: Union[Arrhenius, ArrheniusEP]
    for_reverse: bool
    uncertainty: float
    min_temp: float
    max_temp: float
    min_pressure: float
    max_pressure: float
    collider_species: FrozenSet[ColliderSpecies]
    source: Source
