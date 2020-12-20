from django_test_migrations.contrib.unittest_case import MigratorTestCase
from database.templatetags.utils import fields
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

    def _find_kinetics_data(self, kinetics):
        for model_name in [
            "Arrhenius",
            "ArrheniusEP",
            "Chebyshev",
            "KineticsData",
            "Lindemann",
            "MultiArrhenius",
            "PDepArrhenius",
            "MultiPDepArrhenius",
            "Troe",
            "ThirdBody",
        ]:
            model = self.model(model_name)
            try:
                return model.objects.get(kinetics=kinetics)
            except model.DoesNotExist:
                continue

    def _get_kinetics_hash(self, kinetics):
        source_id = kinetics.source.id if kinetics.source else ""
        bd = kinetics.base_data
        data = "".join(x[1] for x in fields(self._find_kinetics_data(kinetics))) if bd else ""
        base_data_signature = (
            "".join(
                str(x)
                for x in [
                    bd.order,
                    bd.min_temp,
                    bd.max_temp,
                    bd.min_pressure,
                    bd.max_pressure,
                    *bd.collider_efficiencies.values_list("id", flat=True),
                ]
            )
            if bd
            else ""
        )
        signature = "".join(
            str(x)
            for x in [
                kinetics.prime_id,
                kinetics.reaction.id,
                source_id,
                kinetics.reverse,
                base_data_signature,
                data,
            ]
        )

        return hash(signature)

    def test_unique_kinetics(self):
        Kinetics = self.model("Kinetics")
        hashes = [self._get_kinetics_hash(k) for k in Kinetics.objects.all()]

        self.assertEqual(len(hashes), len(set(hashes)))
