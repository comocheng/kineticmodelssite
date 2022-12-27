from backend.database.event_store import EventStore
from backend.models.kinetic_model import KineticModel


def test_event_store(kinetic_model: KineticModel, event_store: EventStore):
    event_store.append_kinetic_model(kinetic_model)
    assert event_store.get_kinetic_model(0).id == kinetic_model.id
