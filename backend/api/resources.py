from fastapi import Depends

from backend.database.event_source import EventSource
from backend.database.event_store import EventStore
from backend.database.list_event_store import ListEventStore
from backend.database.model_repository import ModelRepository


event_store = ListEventStore()
repo = ModelRepository()


def get_event_store() -> EventStore:
    return event_store


def get_model_repo() -> ModelRepository:
    return repo


def get_event_source(event_store: EventStore = Depends(get_event_store), model_repo: ModelRepository = Depends(get_model_repo)) -> EventSource:
    event_source = EventSource(event_store, [model_repo])
    event_source.catch_up_observers()

    return event_source
