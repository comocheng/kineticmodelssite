from backend.models.kinetic_model import KineticModel
from backend.database.event_store import EventStore
from backend.database.event_observer import EventObserver

class EventSource:
    def __init__(self, event_store: EventStore, observers: list[EventObserver]) -> None:
        self.event_store = event_store
        self.observers = observers

    def update(self, kinetic_model: KineticModel) -> None:
        self.event_store.append_kinetic_model(kinetic_model)
        for o in self.observers:
            o.accept(kinetic_model)

    def catch_up_observers(self) -> None:
        for o in self.observers:
            o.catch_up(self.event_store.get_all_kinetic_models())
