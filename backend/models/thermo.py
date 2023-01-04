from pydantic import Field

from backend.models.model import Model
from backend.models.source import Source
from backend.models.species import Species


class Thermo(Model):
    species: Species
    min_temp1: float
    max_temp1: float
    min_temp2: float
    max_temp2: float
    source: Source
    preferred_key: str | None
    reference_temp: float | None
    reference_pressure: float | None
    enthalpy_formation: float | None
    prime_id: str | None = None
    polynomial1: list[float] = Field(min_items=7, max_items=7)
    polynomial2: list[float] = Field(min_items=7, max_items=7)
