from typing import Iterable
from backend.models.kinetic_model import KineticModel
from .event_store import EventStore

class ListEventStore(EventStore):
    def __init__(self) -> None:
        self.models: list[KineticModel] = []

    def get_kinetic_model(self, position: int) -> KineticModel | None:
        try:
            return self.models[position]
        except IndexError:
            return None

    def get_all_kinetic_models(self) -> Iterable[KineticModel]:
        return self.models

    def append_kinetic_model(self, kinetic_model: KineticModel) -> None:
        self.models.append(kinetic_model)
