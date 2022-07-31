from backend.models.source import Source
from backend.models.species import Species
from backend.models.utils import frozen_dataclass


@frozen_dataclass
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
