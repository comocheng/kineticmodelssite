import unittest

from hypothesis import given, settings, strategies

from backend.database import Database
from backend.models.kinetic_model import KineticModel


class DatabaseTest(unittest.TestCase):
    def _test_import_kinetic_model(self, database: Database, kinetic_model: KineticModel):
        self.assertIn(kinetic_model, database.kinetic_models)
        self.assertCountEqual(kinetic_model.kinetics, database.kinetics)
        self.assertCountEqual(kinetic_model.thermo, database.thermo)
        self.assertCountEqual(kinetic_model.transport, database.transport)
        species = [ns.species for ns in kinetic_model.named_species]
        self.assertCountEqual(species, database.species)
        self.assertIn(kinetic_model.source, database.sources)

    @given(strategies.builds(KineticModel))
    @settings(max_examples=10)
    def test_import_kinetic_model(self, kinetic_model: KineticModel):
        database = Database()
        database.import_kinetic_model(kinetic_model)
        self._test_import_kinetic_model(database, kinetic_model)

    @given(strategies.builds(KineticModel))
    @settings(max_examples=10)
    def test_idempotency(self, kinetic_model: KineticModel):
        database = Database()
        database.import_kinetic_model(kinetic_model)
        database.import_kinetic_model(kinetic_model)
        self._test_import_kinetic_model(database, kinetic_model)
