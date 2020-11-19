from django.core.exceptions import MultipleObjectsReturned
from django.test import TestCase
from django_test_migrations.contrib.unittest_case import MigratorTestCase
from database import models
from database.scripts.import_rmg_models import *


class TestImportRmgModelsIntegration(MigratorTestCase):
    migrate_from = ("database", "0001_initial")
    migrate_to = ("database", "import_rmg_models")

    def model(self, model_name):
        return self.new_state.apps.get_model("database", model_name)

    def test_consistent_species_hash(self):
        Species = self.model("Species")
        self.assertTrue(
            all(get_species_hash(s.structures.all()) == s.hash for s in Species.objects.all())
        )

    def test_consistent_reaction_hash(self):
        Reaction = self.model("Reaction")
        self.assertTure(
            all(get_reaction_hash(r.stoich_species()) == r.hash for r in Reaction.objects.all())
        )


class TestImportRmgModelsUnit(TestCase):
    def test_get_or_create_reaction_from_stoich_set(self):
        """
        A Reaction with a unique set of stoich-species pairs should be found if the entire set of pairs is queried.

        A partial match should create a new Reaction.
        A partial match and an exact match should return the exact match.
        Multiple partial matches should create a new Reaction.
        Multiple exact matches should throw MultipleObjectsReturned.
        """

        formula_a = models.Formula.objects.create(formula="A")
        formula_b = models.Formula.objects.create(formula="B")
        formula_c = models.Formula.objects.create(formula="C")
        formula_d = models.Formula.objects.create(formula="D")
        species_a = models.Species.objects.create(scope="*", formula=formula_a)
        species_b = models.Species.objects.create(formula=formula_b)
        species_c = models.Species.objects.create(formula=formula_c)
        species_d = models.Species.objects.create(formula=formula_d)
        reaction1 = models.Reaction.objects.create(reversible=False)
        reaction2 = models.Reaction.objects.create(reversible=False)
        reaction3 = models.Reaction.objects.create(reversible=True)
        reaction4 = models.Reaction.objects.create(reversible=True)
        reaction1.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction1.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction1.species.add(species_c, through_defaults={"stoichiometry": 1})
        reaction1.save()
        reaction2.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction2.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction2.species.add(species_c, through_defaults={"stoichiometry": 1})
        reaction2.species.add(species_d, through_defaults={"stoichiometry": 1})
        reaction2.save()
        reaction3.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction3.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction3.save()
        reaction4.species.add(species_a, through_defaults={"stoichiometry": -1})
        reaction4.species.add(species_b, through_defaults={"stoichiometry": 1})
        reaction4.save()

        stoich_data_exact_match = [(-1, species_a), (1, species_b), (1, species_c), (1, species_d)]
        stoich_data_exact_match_multiple = [(-1, species_a), (1, species_b)]
        stoich_data_partial_match = [(-1, species_a), (1, species_c), (1, species_d)]
        stoich_data_partial_match_multiple = [(-1, species_a)]
        stoich_data_exact_partial_match = [(-1, species_a), (1, species_b), (1, species_c)]
        _models = {"Reaction": models.Reaction}

        exact_match_reaction, exact_match_created = get_or_create_reaction_from_stoich_data(
            stoich_data_exact_match, _models, reversible=False
        )
        _, multiple_partial_match_created = get_or_create_reaction_from_stoich_data(
            stoich_data_partial_match_multiple, _models, reversible=False
        )
        _, partial_match_created = get_or_create_reaction_from_stoich_data(
            stoich_data_partial_match, _models, reversible=False
        )
        (
            exact_partial_match_reaction,
            exact_partial_match_created,
        ) = get_or_create_reaction_from_stoich_data(
            stoich_data_exact_partial_match, _models, reversible=False
        )

        self.assertFalse(exact_match_created)
        self.assertEqual(reaction2, exact_match_reaction)
        self.assertTrue(partial_match_created)
        self.assertTrue(multiple_partial_match_created)
        self.assertRaises(
            MultipleObjectsReturned,
            get_or_create_reaction_from_stoich_data,
            stoich_data_exact_match_multiple,
            _models,
            reversible=True,
        )
        self.assertFalse(exact_partial_match_created)
        self.assertEqual(reaction1, exact_partial_match_reaction)
