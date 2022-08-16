import pytest
from fastapi.testclient import TestClient

from backend.api.db import get_db
from backend.database import Database, ObjectDatabase
from backend.main import app

db = ObjectDatabase()

def get_test_db() -> Database:
    return db


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        app.dependency_overrides[get_db] = get_test_db
        yield client
        del app.dependency_overrides[get_db]
