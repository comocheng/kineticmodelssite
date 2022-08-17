from dataclasses import field
from uuid import UUID, uuid4

from pydantic import confrozenset
from pydantic.dataclasses import dataclass

from backend.models.kinetics import Kinetics
from backend.models.model import Model
from backend.models.source import Source
from backend.models.species import Species
from backend.models.thermo import Thermo
from backend.models.transport import Transport


class NamedSpecies(Model):
    name: str
    species: Species


class KineticModel(Model):
    name: str
    prime_id: str
    named_species: confrozenset(NamedSpecies)
    kinetics: confrozenset(Kinetics)
    thermo: confrozenset(Thermo)
    transport: confrozenset(Transport)
    source: Source
