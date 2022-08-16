from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import builds

from backend.database import ObjectDatabase
from backend.models.kinetic_model import KineticModel


@given(kinetic_model=builds(KineticModel))
@settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_import_kinetic_models(kinetic_model: KineticModel, database: ObjectDatabase):
    database.import_kinetic_model(kinetic_model)
    assert kinetic_model == database.kinetic_models[kinetic_model.id]
    assert kinetic_model.source == database.sources[kinetic_model.source.id]
    assert all(kinetics == database.kinetics[kinetics.id] for kinetics in kinetic_model.kinetics)
    assert all(thermo == database.thermo[thermo.id] for thermo in kinetic_model.thermo)
    assert all(
        transport == database.transport[transport.id] for transport in kinetic_model.transport
    )
    assert all(ns.species == database.species[ns.species.id] for ns in kinetic_model.named_species)
