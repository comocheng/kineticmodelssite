import unittest

from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies, HealthCheck
from backend.database import ObjectDatabase
from backend.models.kinetic_model import KineticModel
from backend.api import app, get_db
from fastapi.encoders import jsonable_encoder



class ApiTest(unittest.TestCase):
    @given(strategies.builds(KineticModel))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_api(self, kinetic_model: KineticModel):
        print(kinetic_model)
        database = ObjectDatabase()
        app.dependency_overrides[get_db] = lambda: database
        client = TestClient(app)
        client.post("/kinetic_model", json=jsonable_encoder(kinetic_model))
        response = client.get("/kinetic_model/0")
        traveled_model = KineticModel(**response.json())
        self.assertEqual(kinetic_model, traveled_model)
