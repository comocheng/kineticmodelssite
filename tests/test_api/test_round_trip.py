import hypothesis.strategies as st
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings

from backend.models.kinetic_model import KineticModel


@given(kinetic_model=st.builds(KineticModel))
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_round_trip(kinetic_model: KineticModel, client: TestClient):
    encoded = jsonable_encoder(kinetic_model)
    client.post("/kinetic_model", json=encoded)
    response = client.get(f"/kinetic_model/{kinetic_model.id}")
    traveled_model = KineticModel(**response.json())
    assert kinetic_model.id == traveled_model.id
