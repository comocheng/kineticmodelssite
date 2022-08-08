from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import builds

from backend.database import ObjectDatabase
from backend.models.kinetic_model import KineticModel


@given(kinetic_model=builds(KineticModel))
@settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_import_kinetic_models(kinetic_model: KineticModel, database: ObjectDatabase):
    database.import_kinetic_model(kinetic_model)
    assert kinetic_model in database.kinetic_models
    assert kinetic_model.source in database.sources
    assert all(kinetics in database.kinetics for kinetics in kinetic_model.kinetics)
    assert all(thermo in database.thermo for thermo in kinetic_model.thermo)
    assert all(transport in database.transport for transport in kinetic_model.transport)
    assert all(ns.species in database.species for ns in kinetic_model.named_species)
