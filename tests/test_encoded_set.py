from typing import List

from hypothesis import given, settings, strategies

from backend.database.object_database import EncodedSet
from backend.models.kinetic_model import KineticModel


@given(strategies.builds(KineticModel))
@settings(max_examples=10)
def test_encoded_set(kinetic_model: KineticModel):
    encoded_set = EncodedSet(factory=KineticModel)
    encoded_set.add(kinetic_model)
    assert 1 == len(encoded_set)
    assert kinetic_model in encoded_set


@given(strategies.lists(strategies.builds(KineticModel)))
@settings(max_examples=10)
def test_encoded_set_multi(kinetic_models: List[KineticModel]):
    encoded_set = EncodedSet(factory=KineticModel)
    for km in kinetic_models:
        encoded_set.add(km)
    assert len(kinetic_models) == len(encoded_set)
    assert all(km in encoded_set for km in kinetic_models)
