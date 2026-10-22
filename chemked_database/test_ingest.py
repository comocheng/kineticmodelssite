"""
Tests for the ingest-after-merge path (sync_chemked --files) and the shared
ChemKED import used by the REST contribution API.

Kept apart from tests.py, which needs pyked.batch_convert.
"""

import os
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .import_dispatcher import import_chemked_to_db
from .models import ExperimentDataset

TESTDATA = Path(__file__).resolve().parent / "testdata"
FIXTURE_NAME = "Test_2020_ST_7.yaml"


class SyncChemkedIngestTests(TestCase):
    """What the chemked-ingest workflow runs after a merge."""

    def _sync(self, *files, **options):
        call_command(
            "sync_chemked", files=list(files), stdout=StringIO(), stderr=StringIO(), **options
        )

    def test_settings_path_is_the_default(self):
        with self.settings(CHEMKED_DATABASE_PATH=str(TESTDATA)):
            self._sync(FIXTURE_NAME)

        dataset = ExperimentDataset.objects.get(chemked_file_path=FIXTURE_NAME)
        self.assertEqual(dataset.datapoints.count(), 2)

    def test_reingest_replaces_datapoints(self):
        self._sync(FIXTURE_NAME, path=str(TESTDATA))
        self._sync(FIXTURE_NAME, path=str(TESTDATA))

        dataset = ExperimentDataset.objects.get(chemked_file_path=FIXTURE_NAME)
        self.assertEqual(dataset.datapoints.count(), 2)

    def test_missing_file_fails_the_command(self):
        with self.assertRaises(CommandError):
            self._sync("no-such-dir/missing.yaml", path=str(TESTDATA))


class ChemkedDatabasePathSettingTests(TestCase):
    def test_setting_is_defined(self):
        expected = os.getenv(
            "CHEMKED_DATABASE_PATH",
            os.path.join(os.path.dirname(settings.BASE_DIR), "ChemKED-database"),
        )
        self.assertEqual(settings.CHEMKED_DATABASE_PATH, expected)


class ImportChemkedToDbTests(TestCase):
    """The API's import_to_db option uses the web upload's importer."""

    def test_imports_yaml_bytes(self):
        dataset = import_chemked_to_db(
            (TESTDATA / FIXTURE_NAME).read_bytes(), FIXTURE_NAME, file_author="Test Author"
        )

        self.assertEqual(dataset.datapoints.count(), 2)
        self.assertEqual(dataset.reference_year, 2020)
        self.assertEqual(dataset.experiment_type, "ignition delay")

    def test_custom_dataset_name(self):
        dataset = import_chemked_to_db(
            (TESTDATA / FIXTURE_NAME).read_text(), FIXTURE_NAME, dataset_name="api-test"
        )

        self.assertEqual(dataset.chemked_file_path, "api-test")

    def test_rejects_non_mapping(self):
        with self.assertRaises(ValueError):
            import_chemked_to_db(b"- just\n- a list\n", "bad.yaml")
