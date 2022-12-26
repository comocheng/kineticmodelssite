from abc import abstractmethod
from typing import Iterable, Protocol, runtime_checkable

from backend.models.kinetic_model import KineticModel


@runtime_checkable
class EventStore(Protocol):
    @abstractmethod
    def get_kinetic_model(self, id: int) -> KineticModel:
        ...

    @abstractmethod
    def get_all_kinetic_models(self) -> Iterable[KineticModel]:
        ...

    @abstractmethod
    def append_kinetic_model(self, kinetic_model: KineticModel) -> None:
        ...
