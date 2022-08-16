from dataclasses import field
from uuid import UUID, uuid4

from pydantic import conlist
from pydantic.dataclasses import dataclass

from backend.models.kinetics import Kinetics
from backend.models.source import Source
from backend.models.species import Species
from backend.models.thermo import Thermo
from backend.models.transport import Transport


@dataclass(frozen=True)
class NamedSpecies:
    name: str
    species: Species


@dataclass(frozen=True)
class KineticModel:
    name: str
    prime_id: str
    named_species: conlist(NamedSpecies, min_items=0, unique_items=True)
    kinetics: conlist(Kinetics, unique_items=True)
    thermo: conlist(Thermo, unique_items=True)
    transport: conlist(Transport, unique_items=True)
    source: Source
    id: UUID = field(default_factory=uuid4, compare=False)
