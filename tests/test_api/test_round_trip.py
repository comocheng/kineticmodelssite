import hypothesis.strategies as st
from apischema import deserialize, serialize
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings

from backend.models.kinetic_model import KineticModel


@given(kinetic_model=st.builds(KineticModel))
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_round_trip(kinetic_model: KineticModel, client: TestClient):
    client.post("/kinetic_model", json=serialize(kinetic_model))
    response = client.get(f"/kinetic_model/{kinetic_model.id}")
    traveled_model = KineticModel(**response.json())
    assert kinetic_model == traveled_model
