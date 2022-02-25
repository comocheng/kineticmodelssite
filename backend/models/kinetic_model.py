from typing import List

from pydantic import BaseModel

from .species import Species
from .kinetics import Kinetics
from .thermo import Thermo
from .transport import Transport
from .source import Source

class NamedSpecies(BaseModel):
    name: str
    species: Species


class KineticModel(BaseModel):
    name: str
    prime_id: str
    named_species: List[NamedSpecies]
    kinetics: List[Kinetics]
    thermo: List[Thermo]
    transport: List[Transport]
    source: Source
