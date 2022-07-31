from typing import FrozenSet

from backend.models.kinetics import Kinetics
from backend.models.source import Source
from backend.models.species import Species
from backend.models.thermo import Thermo
from backend.models.transport import Transport
from backend.models.utils import frozen_dataclass


@frozen_dataclass
class NamedSpecies:
    name: str
    species: Species


@frozen_dataclass
class KineticModel:
    name: str
    prime_id: str
    named_species: FrozenSet[NamedSpecies]
    kinetics: FrozenSet[Kinetics]
    thermo: FrozenSet[Thermo]
    transport: FrozenSet[Transport]
    source: Source
