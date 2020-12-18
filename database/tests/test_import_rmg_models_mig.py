from django_test_migrations.contrib.unittest_case import MigratorTestCase
from database.scripts.import_rmg_models import (
    get_reaction_hash,
    get_species_hash,
)


class TestImportRmgModelsIntegration(MigratorTestCase):
    migrate_from = ("database", "0001_initial")
    migrate_to = ("database", "import_rmg_models")

    def model(self, model_name):
        return self.new_state.apps.get_model("database", model_name)

    def test_consistent_species_hash(self):
        Species = self.model("Species")
        self.assertTrue(
            all(get_species_hash(s.isomers.all()) == s.hash for s in Species.objects.all())
        )

    def test_consistent_reaction_hash(self):
        Reaction = self.model("Reaction")
        for reaction in Reaction.objects.all():
            stoich_species = [
                (s.stoichiometry, s.species) for s in reaction.stoichiometry_set.all()
            ]
            self.assertTrue(
                get_reaction_hash(stoich_species) == reaction.hash,
                f"Reaction {reaction} has inconsistent hash with its stoich-species pairs",
            )
