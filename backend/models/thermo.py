from typing import List

from pydantic import BaseModel

from .species import Species
from .source import Source


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
