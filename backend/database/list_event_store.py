from typing import Iterable
from backend.models.kinetic_model import KineticModel
from .event_store import EventStore

class ListEventStore(EventStore):
    def __init__(self) -> None:
        self._kinetic_models: list[KineticModel] = []

    def get_kinetic_model(self, id: int) -> KineticModel | None:
        try:
            return self._kinetic_models[id]
        except IndexError:
            return None

    def get_all_kinetic_models(self) -> Iterable[KineticModel]:
        return self._kinetic_models

    def append_kinetic_model(self, kinetic_model: KineticModel) -> None:
        self._kinetic_models.append(kinetic_model)
