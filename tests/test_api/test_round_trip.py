from apischema import deserialize, serialize

from fastapi.testclient import TestClient
from backend.models.kinetic_model import KineticModel


def test_round_trip(kinetic_model: KineticModel, client: TestClient):
    client.post("/kinetic_model", json=serialize(kinetic_model))
    response = client.get("/kinetic_model/0")
    traveled_model = deserialize(KineticModel, response.json())
    assert kinetic_model == traveled_model
