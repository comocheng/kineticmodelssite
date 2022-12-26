from backend.database.event_model import EventModel
from backend.database.event_store import EventStore
from backend.database.list_event_store import ListEventStore

event_store = ListEventStore()
event_model = EventModel(event_store)

def get_event_store() -> EventStore:
    return event_store

def get_event_model() -> EventModel:
    return event_model
