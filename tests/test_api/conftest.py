import json
from apischema import deserialize
import pytest
from fastapi.testclient import TestClient
from backend.api.db import get_db
from backend.database import ObjectDatabase
from backend.database import Database
from backend.main import app
from backend.models.kinetic_model import KineticModel


def get_test_db() -> Database:
    return ObjectDatabase()

@pytest.fixture()
def client():
    with TestClient(app) as client:
        app.dependency_overrides[get_db] = get_test_db
        yield client
        del app.dependency_overrides[get_db]

@pytest.fixture
def kinetic_model() -> KineticModel:
    with open("tests/km.json", "r") as f:
        return deserialize(KineticModel, json.load(f))
