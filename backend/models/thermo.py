from typing import FrozenSet

from backend.models.source import Source
from backend.models.species import Species
from backend.models.utils import Model


class Thermo(Model):
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
