from dataclasses import field
from uuid import UUID, uuid4

from pydantic import Field
from pydantic import confrozenset
from pydantic.dataclasses import dataclass
from backend.models.model import Model

from backend.models.source import Source
from backend.models.species import Species


class Thermo(Model):
    prime_id: str
    preferred_key: str
    species: Species
    reference_temp: float
    reference_pressure: float
    enthalpy_formation: float
    polynomial1: confrozenset(float, min_items=0, max_items=7)
    polynomial2: confrozenset(float, min_items=0, max_items=7)
    min_temp1: float
    max_temp1: float
    min_temp2: float
    max_temp2: float
    source: Source
