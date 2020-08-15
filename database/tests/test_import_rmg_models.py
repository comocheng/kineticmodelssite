from django.core.exceptions import MultipleObjectsReturned
from django.test import TestCase
from database import models
from database.migrations.import_rmg_models import *


class TestImportRmgModels(TestCase):
    def get_reaction_from_stoich_set(self):
        species_a = models.Species.objects.create(formula="A")
        species_b = models.Species.objects.create(formula="B")
        species_c = models.Species.objects.create(formula="C")
        reaction1 = models.Reaction.objects.create(reversible=False)
        reaction2 = models.Reaction.objects.create(reversible=False)
        reaction3 = models.Reaction.objects.create(reversible=True)
        stoich_a1 = models.Stoichiometry.create(reaction=reaction1, species=species_a, stoichiometry=-1)
        stoich_b1 = models.Stoichiometry.create(reaction=reaction1, species=species_b, stoichiometry=1)
        stoich_a2 = models.Stoichiometry.create(reaction=reaction2, species=species_a, stoichiometry=-1)
        stoich_b2 = models.Stoichiometry.create(reaction=reaction2, species=species_b, stoichiometry=1)
        stoich_c2 = models.Stoichiometry.create(reaction=reaction2, species=species_c, stoichiometry=1)
        stoich_a3 = models.Stoichiometry.create(reaction=reaction3, species=species_a, stoichiometry=-1)
        stoich_b3 = models.Stoichiometry.create(reaction=reaction3, species=species_b, stoichiometry=1)

        stoich_data_2 = [(-1, species_a), (1, species_b), (1, species_c)]
        stoich_data_1 = [(-1, species_a), (1, species_b)]
        stoich_data_missing = [(-1, species_a), (1, species_c)]
        _models = {"Reaction": models.Reaction}

        self.assertEqual(reaction1, get_reaction_from_stoich_set(stoich_data_2, **_models))
        self.assertRaises(MultipleObjectsReturned, get_reaction_from_stoich_set(stoich_data_1, **_models))
        self.assertRaises(models.Reaction.DoesNotExist, get_reaction_from_stoich_set(stoich_data_missing, **_models))
