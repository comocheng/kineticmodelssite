from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from backend.models.kinetic_model import KineticModel

def test_round_trip(kinetic_model: KineticModel, client: TestClient):
    encoded = jsonable_encoder(kinetic_model)
    client.post("/kinetic_model", json=encoded)
    response = client.get(f"/kinetic_model/{kinetic_model.id}")
    traveled_model = KineticModel.parse_obj(response.json())
    assert kinetic_model.id == traveled_model.id
