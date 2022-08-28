
from backend.models.model import Model
from backend.models.source import Source
from backend.models.species import Species


class Transport(Model):
    species: Species
    geometry: float
    well_depth: float
    collision_diameter: float
    dipole_moment: float
    polarizability: float
    rotational_relaxation: float
    source: Source
    prime_id: str | None = None
