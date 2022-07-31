from typing import FrozenSet

from .utils import frozen_dataclass

from .species import Species
from .kinetics import Kinetics
from .thermo import Thermo
from .transport import Transport
from .source import Source

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
