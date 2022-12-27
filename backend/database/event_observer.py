from abc import abstractmethod
from typing import Iterable, Protocol, runtime_checkable

from backend.models.kinetic_model import KineticModel


@runtime_checkable
class EventObserver(Protocol):
    @abstractmethod
    def accept(self, kinetic_model: KineticModel) -> None:
        ...

    @abstractmethod
    def catch_up(self, kinetic_models: Iterable[KineticModel]) -> None:
        ...
