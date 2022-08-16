from abc import abstractmethod
from typing import Iterable, Protocol, runtime_checkable
from uuid import UUID

from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport


@runtime_checkable
class Database(Protocol):
    @abstractmethod
    def get_kinetic_model(self, uuid: UUID) -> KineticModel:
        ...

    @abstractmethod
    def get_kinetics(self, uuid: UUID) -> Kinetics:
        ...

    @abstractmethod
    def get_thermo(self, uuid: UUID) -> Thermo:
        ...

    @abstractmethod
    def get_transport(self, uuid: UUID) -> Transport:
        ...

    @abstractmethod
    def get_reaction(self, uuid: UUID) -> Reaction:
        ...

    @abstractmethod
    def get_species(self, uuid: UUID) -> Species:
        ...

    @abstractmethod
    def get_isomer(self, uuid: UUID) -> Isomer:
        ...

    @abstractmethod
    def get_structure(self, uuid: UUID) -> Structure:
        ...

    @abstractmethod
    def get_all_kinetic_models(self) -> Iterable[KineticModel]:
        ...

    @abstractmethod
    def get_all_kinetics(self) -> Iterable[Kinetics]:
        ...

    @abstractmethod
    def get_all_thermo(self) -> Iterable[Thermo]:
        ...

    @abstractmethod
    def get_all_transport(self) -> Iterable[Transport]:
        ...

    @abstractmethod
    def get_all_reactions(self) -> Iterable[Reaction]:
        ...

    @abstractmethod
    def get_all_species(self) -> Iterable[Species]:
        ...

    @abstractmethod
    def get_all_isomers(self) -> Iterable[Isomer]:
        ...

    @abstractmethod
    def get_all_structures(self) -> Iterable[Structure]:
        ...

    @abstractmethod
    def import_kinetic_model(self, kinetic_model: KineticModel) -> None:
        ...

    @abstractmethod
    def import_source(self, source: Source) -> None:
        ...

    @abstractmethod
    def import_kinetics(self, kinetics: Kinetics) -> None:
        ...

    @abstractmethod
    def import_thermo(self, thermo: Thermo) -> None:
        ...

    @abstractmethod
    def import_transport(self, transport: Transport) -> None:
        ...

    @abstractmethod
    def import_reaction(self, reaction: Reaction) -> None:
        ...

    @abstractmethod
    def import_species(self, species: Species) -> None:
        ...

    @abstractmethod
    def import_isomer(self, isomer: Isomer) -> None:
        ...

    @abstractmethod
    def import_structure(self, structure: Structure) -> None:
        ...
