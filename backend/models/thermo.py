from typing import FrozenSet

from .utils import frozen_dataclass
from .species import Species
from .source import Source


@frozen_dataclass
class Thermo:
    prime_id: str
    preferred_key: str
    species: Species
    reference_temp: float
    reference_pressure: float
    enthalpy_formation: float
    polynomial1: FrozenSet[float]
    polynomial2: FrozenSet[float]
    min_temp1: float
    max_temp1: float
    min_temp2: float
    max_temp2: float
    source: Source
