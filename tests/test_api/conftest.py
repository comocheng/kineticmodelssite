import pytest
from fastapi.testclient import TestClient

from backend.api.resources import get_event_store
from backend.database.list_event_store import ListEventStore
from backend.database.event_store import EventStore
from backend.main import app


event_store = ListEventStore()


def get_test_event_store() -> EventStore:
    return event_store


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        app.dependency_overrides[get_event_store] = get_test_event_store
        yield client
        del app.dependency_overrides[get_event_store]
