from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.models.kinetic_model import KineticModel


def test_out_of_bounds(kinetic_model: KineticModel, client: TestClient):
    response = client.get(f"/kinetic_model/{kinetic_model.id}")
    assert 404 == response.status_code
