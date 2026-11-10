"""ChemKED datasets that match a ChemKED-database checkout (prune_chemked_datasets, sync_chemked).

The database holds the files of the repository's main branch and nothing else: no dataset the
web pages stored without a file, no dataset of a moved file, and no second copy of a file's
compositions and values after a re-ingest. Kept apart from tests.py, which needs
pyked.batch_convert.
"""

import shutil
import tempfile
from io import StringIO
from pathlib import Path

import yaml
from django.apps import apps
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from analysis.models import SimulationRun
from database.models import KineticModel

from .management.commands.sync_chemked import store_chemked_data, value_relations
from .models import (
    Composition,
    CompositionSpecies,
    ExperimentDataset,
    SpeciationMeasurementDatapoint,
    ValueWithUnit,
)
from .test_ingest import SPECIATION_FILE

TESTDATA = Path(__file__).resolve().parent / "testdata"
IN_MAIN = "hydrogen/Test_2020/Test_2020_ST_7.yaml"


def unused_values():
    used = set()
    for rel in value_relations():
        used.update(
            rel.related_model.objects.exclude(**{f"{rel.field.name}__isnull": True})
            .values_list(rel.field.attname, flat=True)
        )
    return ValueWithUnit.objects.exclude(id__in=used).count()


def counts():
    return {
        "datasets": ExperimentDataset.objects.count(),
        "compositions": Composition.objects.count(),
        "species": CompositionSpecies.objects.count(),
        "values": ValueWithUnit.objects.count(),
    }


class ChemkedCheckout(TestCase):
    """A checkout with one file, stored once from the checkout, and two datasets without a file."""

    def setUp(self):
        self.checkout = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.checkout)
        target = self.checkout / IN_MAIN
        target.parent.mkdir(parents=True)
        shutil.copy(TESTDATA / "Test_2020_ST_7.yaml", target)
        self.data = yaml.safe_load(target.read_text())

    def sync(self):
        call_command("sync_chemked", path=str(self.checkout), stdout=StringIO(), stderr=StringIO())

    def prune(self, *args):
        out = StringIO()
        call_command("prune_chemked_datasets", "--path", str(self.checkout), *args, stdout=out)
        return out.getvalue()


class ValueRelationTests(SimpleTestCase):
    def test_every_foreign_key_to_a_value_is_found(self):
        keys = {
            (model._meta.label, field.name)
            for model in apps.get_models()
            for field in model._meta.concrete_fields
            if field.is_relation and field.related_model is ValueWithUnit
        }
        found = {(rel.related_model._meta.label, rel.field.name) for rel in value_relations()}
        self.assertEqual(found, keys)
        # A relation without a reverse accessor (related_name "+")
        self.assertIn(("chemked_database.SpeciationMeasurementDatapoint", "residence_time_quantity"), found)


class SpeciationValuesTests(ChemkedCheckout):
    def setUp(self):
        super().setUp()
        target = self.checkout / "hydrogen/Cong_2009/Cong_2009_JSR.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(SPECIATION_FILE)

    def test_reingest_and_prune_keep_the_speciation_quantities(self):
        self.sync()
        first = counts()
        self.sync()
        self.assertEqual(counts(), first)
        self.prune("--apply")
        self.assertEqual(counts(), first)
        self.assertEqual(unused_values(), 0)
        point = SpeciationMeasurementDatapoint.objects.get()
        self.assertIsNotNone(point.residence_time_quantity)
        self.assertIsNotNone(point.reactor_volume_quantity)


class ReingestTests(ChemkedCheckout):
    def test_a_second_ingest_leaves_no_second_copy(self):
        self.sync()
        first = counts()
        self.sync()
        self.assertEqual(counts(), first)
        self.assertFalse(Composition.objects.filter(datapoints__isnull=True, common_properties__isnull=True).exists())


class PruneTests(ChemkedCheckout):
    def setUp(self):
        super().setUp()
        self.sync()
        self.kept = counts()
        # Stored by the web pages under a flat name, and a file that moved in the repository
        store_chemked_data(self.data, "H2_Test_2020_ST_10004084", lambda message: None)
        store_chemked_data(self.data, "hydrogen/Old_folder/Test_2020_ST_7.yaml", lambda message: None)
        # A composition that an earlier re-ingest left behind
        left = Composition.objects.create(kind="mole fraction")
        CompositionSpecies.objects.create(composition=left, species_name="O2", amount=0.2)

    def test_dry_run_writes_nothing(self):
        before = counts()
        out = self.prune()
        self.assertEqual(counts(), before)
        self.assertIn("2 without", out)
        self.assertIn("1 with a flat name", out)
        self.assertIn("1 with a repository path not in the checkout", out)
        self.assertIn("rolled back", out)

    def test_only_the_files_of_the_checkout_stay(self):
        self.prune("--apply")
        self.assertEqual(list(ExperimentDataset.objects.values_list("chemked_file_path", flat=True)), [IN_MAIN])
        self.assertEqual(counts(), self.kept)

    def test_a_second_run_changes_nothing(self):
        self.prune("--apply")
        out = self.prune("--apply")
        self.assertIn("0 without", out)
        self.assertIn("Unused rows deleted: 0 compositions with 0 species", out)

    def test_report_lists_the_deleted_datasets(self):
        report = self.checkout / "deleted.csv"
        self.prune("--report", str(report))
        rows = report.read_text().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertIn("H2_Test_2020_ST_10004084", rows[1])

    def test_runs_stay_without_a_dataset_unless_asked(self):
        model = KineticModel.objects.create(model_name="a")
        flat = ExperimentDataset.objects.get(chemked_file_path="H2_Test_2020_ST_10004084")
        kept = ExperimentDataset.objects.get(chemked_file_path=IN_MAIN)
        run = SimulationRun.objects.create(kinetic_model=model, dataset=flat)
        SimulationRun.objects.create(kinetic_model=model, dataset=kept)

        out = self.prune("--apply")
        run.refresh_from_db()
        self.assertIsNone(run.dataset)
        self.assertIn("1 simulation runs were on the deleted datasets", out)
        self.assertEqual(SimulationRun.objects.count(), 2)

    def test_with_runs_deletes_the_runs_of_the_deleted_datasets(self):
        model = KineticModel.objects.create(model_name="a")
        flat = ExperimentDataset.objects.get(chemked_file_path="H2_Test_2020_ST_10004084")
        kept = ExperimentDataset.objects.get(chemked_file_path=IN_MAIN)
        SimulationRun.objects.create(kinetic_model=model, dataset=flat)
        SimulationRun.objects.create(kinetic_model=model, dataset=kept)

        self.prune("--apply", "--with-runs")
        self.assertEqual(list(SimulationRun.objects.values_list("dataset_id", flat=True)), [kept.pk])

    def test_a_checkout_without_files_is_refused(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty)
        with self.assertRaises(CommandError):
            call_command("prune_chemked_datasets", "--path", str(empty), "--apply", stdout=StringIO())
        self.assertEqual(ExperimentDataset.objects.count(), 3)
