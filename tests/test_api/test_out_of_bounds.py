from fastapi.testclient import TestClient


def test_out_of_bounds(client: TestClient):
    response = client.get("/kinetic_model/0")
    assert 404 == response.status_code
