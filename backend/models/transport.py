from pydantic import BaseModel

from .species import Species
from .source import Source


class Transport(BaseModel):
    prime_id: str
    species: Species
    geometry: float
    well_depth: float
    collision_diameter: float
    dipole_moment: float
    polarizability: float
    rotational_relaxation: float
    source: Source
