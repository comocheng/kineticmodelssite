from typing import List
import unittest
from hypothesis import given, settings, strategies
from backend.database.object_database import EncodedSet

from backend.models.kinetic_model import KineticModel


class EncodedSetTest(unittest.TestCase):
    @given(strategies.builds(KineticModel))
    @settings(max_examples=10)
    def test_encoded_set(self, kinetic_model: KineticModel):
        encoded_set = EncodedSet(factory=KineticModel)
        encoded_set.add(kinetic_model)
        self.assertEqual(1, len(encoded_set))
        self.assertCountEqual([kinetic_model], encoded_set)

    @given(strategies.lists(strategies.builds(KineticModel)))
    @settings(max_examples=10)
    def test_encoded_set_multi(self, kinetic_models: List[KineticModel]):
        encoded_set = EncodedSet(factory=KineticModel)
        for km in kinetic_models:
            encoded_set.add(km)
        self.assertEqual(len(kinetic_models), len(encoded_set))
        self.assertCountEqual(kinetic_models, encoded_set)
