from dataclasses import field
from uuid import UUID, uuid4

from pydantic.dataclasses import dataclass

from backend.models.source import Source
from backend.models.species import Species


@dataclass(frozen=True)
class Transport:
    prime_id: str
    species: Species
    geometry: float
    well_depth: float
    collision_diameter: float
    dipole_moment: float
    polarizability: float
    rotational_relaxation: float
    source: Source
    id: UUID = field(default_factory=uuid4, compare=False)
