from django.core.exceptions import MultipleObjectsReturned
from django.test import TestCase
from database import models
from database.scripts.import_rmg_models import *


class TestImportRmgModels(TestCase):
    def test_get_or_create_reaction_from_stoich_set(self):
        """
        A Reaction with a unique set of stoich-species pairs should be found if the entire set of pairs is queried.

        A partial match should return a Reaction if the partial match is unique.
        A duplicate reaction or a non-unique partial match should throw MultipleObjectsReturned.
        """

        species_a = models.Species.objects.create(formula="A")
        species_b = models.Species.objects.create(formula="B")
        species_c = models.Species.objects.create(formula="C")
        reaction1 = models.Reaction.objects.create(reversible=False)
        reaction2 = models.Reaction.objects.create(reversible=False)
        reaction3 = models.Reaction.objects.create(reversible=True)
        reaction1.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction1.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction1.save()
        reaction2.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction2.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction2.species.add(species_c, through_defaults={"stoichiometry": 1})
        reaction2.save()
        reaction3.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction3.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction3.save()

        stoich_data_exact_match = [(-1, species_a), (1, species_b), (1, species_c)]
        stoich_data_exact_match_multiple = [(-1, species_a), (1, species_b)]
        stoich_data_partial_match = [(-1, species_a), (1, species_c)]
        stoich_data_partial_match_multiple = [(-1, species_a)]
        _models = {"Reaction": models.Reaction}

        exact_match_reaction, exact_match_created = get_or_create_reaction_from_stoich_data(
            stoich_data_exact_match, _models, reversible=True
        )
        partial_match_reaction, partial_match_created = get_or_create_reaction_from_stoich_data(
            stoich_data_partial_match, _models, reversible=True
        )

        self.assertFalse(exact_match_created)
        self.assertEqual(reaction2, exact_match_reaction)
        self.assertFalse(partial_match_created)
        self.assertEqual(reaction2, partial_match_reaction)
        self.assertRaises(
            MultipleObjectsReturned,
            get_or_create_reaction_from_stoich_data,
            stoich_data_exact_match_multiple,
            _models,
            reversible=True,
        )
        self.assertRaises(
            MultipleObjectsReturned,
            get_or_create_reaction_from_stoich_data,
            stoich_data_partial_match_multiple,
            _models,
            reversible=True,
        )
