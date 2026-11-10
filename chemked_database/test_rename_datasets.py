"""ChemKED files renamed in the repository keep their datasets (rename_chemked_datasets, sync_chemked).

A dataset is keyed by its file's path. A renamed file must keep the same dataset row, so that
its simulation runs, model coverage, SSSOM links and the datapoints of its simulation results
stay linked after prune_chemked_datasets. Each test uses a git clone made in a temporary folder.
"""

import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from analysis.models import DatapointResult, ModelDatasetCoverage, SimulationResult, SimulationRun
from database.models import KineticModel
from provenance.models import SemanticMapping

from .management.commands.sync_chemked import renamed_files
from .models import ExperimentDataset

TESTDATA = Path(__file__).resolve().parent / "testdata"
OLD = "butanol/Togbé_2010/Togbé_2010_ST_7.yaml"
NEW = "butanol/n-butanol/Togbé_2010/Togbé_2010_ST_7.yaml"
URL = "https://github.com/LekiaAnonim/ChemKED-database/blob/main/butanol/Togb%C3%A9_2010/Togb%C3%A9_2010_ST_7.yaml"


class ChemkedClone(TestCase):
    """A git clone with one file, stored from the clone, with a simulation run and its links."""

    def setUp(self):
        self.clone = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.clone)
        self.git("init", "-q")
        self.text = (TESTDATA / "Test_2020_ST_7.yaml").read_text()
        self.write(OLD, self.text)
        self.since = self.commit("first")
        self.sync()

        self.dataset = ExperimentDataset.objects.get(chemked_file_path=OLD)
        self.dataset.data_repository_url = URL
        self.dataset.save()
        self.datapoints = list(self.dataset.datapoints.values_list("pk", flat=True))
        model = KineticModel.objects.create(model_name="a")
        self.run = SimulationRun.objects.create(kinetic_model=model, dataset=self.dataset)
        ModelDatasetCoverage.objects.get_or_create(kinetic_model=model, dataset=self.dataset)
        self.mapping = SemanticMapping.objects.create(
            subject_id="promds:test", object_id="doi:10.1/test", experiment_dataset=self.dataset
        )
        result = SimulationResult.objects.create(simulation_run=self.run)
        self.point = DatapointResult.objects.create(
            simulation_result=result, datapoint_id=self.datapoints[0],
            temperature=1000.0, pressure=1e5, experimental_ignition_delay=1e-3,
        )

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.clone), "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def write(self, rel, text):
        path = self.clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def move(self, old, new):
        (self.clone / new).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", old, new)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def sync(self, *args):
        out = StringIO()
        call_command("sync_chemked", "--path", str(self.clone), *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def rename(self, *args):
        out = StringIO()
        call_command(
            "rename_chemked_datasets", "--path", str(self.clone), "--since", self.since, *args,
            stdout=out, stderr=StringIO(),
        )
        return out.getvalue()

    def prune(self):
        out = StringIO()
        call_command("prune_chemked_datasets", "--path", str(self.clone), "--apply", stdout=out)
        return out.getvalue()

    def assert_links_kept(self, path):
        """The dataset is the same row at *path*, with every link of its simulation run."""
        dataset = ExperimentDataset.objects.get(chemked_file_path=path)
        self.assertEqual(dataset.pk, self.dataset.pk)
        self.run.refresh_from_db()
        self.mapping.refresh_from_db()
        self.assertEqual(self.run.dataset_id, dataset.pk)
        self.assertEqual(self.mapping.experiment_dataset_id, dataset.pk)
        self.assertTrue(ModelDatasetCoverage.objects.filter(dataset=dataset).exists())
        return dataset


class RenamedFilesTests(ChemkedClone):
    def test_git_gives_the_similarity_and_both_paths_unquoted(self):
        self.move(OLD, NEW)
        self.commit("move")
        self.assertEqual(renamed_files(self.clone, self.since), [(100, OLD, NEW)])

    def test_an_unknown_commit_is_refused(self):
        with self.assertRaises(CommandError):
            self.rename("--since", "0" * 40)


class PureRenameTests(ChemkedClone):
    def setUp(self):
        super().setUp()
        self.move(OLD, NEW)
        self.commit("move")

    def test_dry_run_writes_nothing(self):
        out = self.rename()
        self.assertTrue(ExperimentDataset.objects.filter(chemked_file_path=OLD).exists())
        self.assertIn("1 moved\n", out)
        self.assertIn("keep their ids and 1 simulation runs", out)
        self.assertIn("rolled back", out)

    def test_the_dataset_moves_with_its_datapoints_and_links(self):
        self.rename("--apply")
        dataset = self.assert_links_kept(NEW)
        self.assertEqual(list(dataset.datapoints.values_list("pk", flat=True)), self.datapoints)
        self.point.refresh_from_db()
        self.assertEqual(self.point.datapoint_id, self.datapoints[0])
        self.assertEqual(
            dataset.data_repository_url,
            "https://github.com/LekiaAnonim/ChemKED-database/blob/main/butanol/n-butanol/"
            "Togb%C3%A9_2010/Togb%C3%A9_2010_ST_7.yaml",
        )

    def test_the_prune_then_deletes_nothing(self):
        self.rename("--apply")
        self.assertIn("0 without", self.prune())
        self.assert_links_kept(NEW)

    def test_a_second_run_changes_nothing(self):
        self.rename("--apply")
        out = self.rename("--apply")
        self.assertIn("0 moved\n", out)
        self.assertIn("1 already at the new path", out)
        self.assert_links_kept(NEW)

    def test_report_lists_the_renamed_files(self):
        report = self.clone / "renamed.csv"
        self.rename("--report", str(report))
        rows = report.read_text().splitlines()
        self.assertEqual(rows[1], f"{self.dataset.pk},{OLD},{NEW},100,moved,1")

    def test_a_dataset_an_ingest_stored_at_the_new_path_is_replaced(self):
        self.sync("--files", NEW)
        self.assertEqual(ExperimentDataset.objects.count(), 2)
        self.rename("--apply")
        self.assertEqual(ExperimentDataset.objects.count(), 1)
        self.assert_links_kept(NEW)

    def test_a_dataset_with_a_run_at_the_new_path_too_is_left(self):
        self.sync("--files", NEW)
        other = ExperimentDataset.objects.get(chemked_file_path=NEW)
        SimulationRun.objects.create(kinetic_model=KineticModel.objects.get(), dataset=other)
        out = self.rename("--apply")
        self.assertIn("1 a dataset with simulation runs or links at the new path too", out)
        self.assertEqual(ExperimentDataset.objects.get(chemked_file_path=OLD).pk, self.dataset.pk)
        self.assertEqual(ExperimentDataset.objects.get(chemked_file_path=NEW).pk, other.pk)


class ChangedRenameTests(ChemkedClone):
    def test_a_file_moved_and_edited_is_reingested_into_its_dataset(self):
        self.move(OLD, NEW)
        self.write(NEW, self.text.replace("file-version: 0", "file-version: 1"))
        self.commit("move and edit")
        self.assertLess(renamed_files(self.clone, self.since)[0][0], 100)

        out = self.rename("--apply")
        self.assertIn("1 moved, content changed", out)
        dataset = self.assert_links_kept(NEW)
        self.assertEqual(dataset.file_version, 1)

    def test_a_file_edited_under_another_name_is_not_a_rename(self):
        # git pairs a deleted file with a new one of similar text, which may be another experiment
        other = "butanol/n-butanol/Zhang_2012/Zhang_2012_ST_7.yaml"
        self.move(OLD, other)
        self.write(other, self.text.replace("file-version: 0", "file-version: 1"))
        self.commit("delete and add")
        self.assertEqual(renamed_files(self.clone, self.since)[0][1:], (OLD, other))

        out = self.rename("--apply")
        self.assertIn("content and file name changed: not taken for a rename", out)
        self.assertEqual(ExperimentDataset.objects.get().chemked_file_path, OLD)


class SyncRenamedSinceTests(ChemkedClone):
    """The chemked-ingest workflow: sync_chemked --renamed-since with the merged files."""

    def test_a_renamed_file_is_moved_and_not_reingested(self):
        self.move(OLD, NEW)
        self.commit("move")
        out = self.sync("--renamed-since", self.since, "--files", NEW)
        self.assertIn(f"Renamed {OLD} -> {NEW} (R100): moved, dataset {self.dataset.pk}", out)
        self.assertIn("Not re-ingested: 1 renamed files with the same content", out)
        dataset = self.assert_links_kept(NEW)
        self.assertEqual(list(dataset.datapoints.values_list("pk", flat=True)), self.datapoints)
        self.assertIn("0 without", self.prune())

    def test_a_file_moved_and_edited_is_reingested(self):
        self.move(OLD, NEW)
        self.write(NEW, self.text.replace("file-version: 0", "file-version: 1"))
        self.commit("move and edit")
        self.sync("--renamed-since", self.since, "--files", NEW)
        self.assertEqual(self.assert_links_kept(NEW).file_version, 1)

    def test_dry_run_moves_nothing(self):
        self.move(OLD, NEW)
        self.commit("move")
        self.sync("--renamed-since", self.since, "--files", NEW, "--dry-run")
        self.assertEqual(ExperimentDataset.objects.get().chemked_file_path, OLD)
