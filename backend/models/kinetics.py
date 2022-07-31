from typing import FrozenSet, Union

from .utils import frozen_dataclass

from .species import Species
from .reaction import Reaction
from .source import Source

@frozen_dataclass
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

@frozen_dataclass
class ArrheniusEP:
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str


@frozen_dataclass
class ColliderSpecies:
    species: Species
    efficiency: float


@frozen_dataclass
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
    collider_species: FrozenSet[ColliderSpecies]
    source: Source
