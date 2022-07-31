from abc import abstractmethod
from typing import Protocol, Set, runtime_checkable

from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport


@runtime_checkable
class Database(Protocol):
    structures: Set[Structure]
    isomers: Set[Isomer]
    species: Set[Species]
    reactions: Set[Reaction]
    kinetics: Set[Kinetics]
    thermo: Set[Thermo]
    transport: Set[Transport]
    kinetic_models: Set[KineticModel]
    sources: Set[Source]

    @abstractmethod
    def import_kinetic_model(self, kinetic_model: KineticModel) -> None:
        ...

    @abstractmethod
    def import_source(self, source: Source) -> None:
        ...

    def import_kinetics(self, kinetics: Kinetics) -> None:
        ...

    def import_thermo(self, thermo: Thermo) -> None:
        ...

    def import_transport(self, transport: Transport) -> None:
        ...

    def import_reaction(self, reaction: Reaction) -> None:
        ...

    def import_species(self, species: Species) -> None:
        ...

    def import_isomer(self, isomer: Isomer) -> None:
        ...

    def import_structure(self, structure: Structure) -> None:
        ...
