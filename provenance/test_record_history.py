"""What an old canonical URL of a corrected or removed rate or thermo entry shows (the snapshots of
the record keys), and the source commits of the models and datasets (provenance.git_sources)."""
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from chemked_database.management.commands.sync_chemked import store_chemked_data
from chemked_database.models import ExperimentDataset
from chemked_database.test_prune_datasets import IN_MAIN, TESTDATA
from database import models as db
from database.scripts.import_rmg_models import record_source_commits
from database.services.cleanup import MODELS
from provenance.git_sources import Checkout, github_blob
from provenance.models import RecordKey
from provenance.record_key_sync import assign
from provenance.test_record_keys import OH, POLY, RATE, assign_all, reaction, species
from database.services.chemistry_index import index_reactions

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


def repository():
    """A git repository in a temporary folder, removed after the test."""
    folder = Path(tempfile.mkdtemp())
    git(folder, "init", "-q")
    git(folder, "config", "user.email", "test@example.org")
    git(folder, "config", "user.name", "Test")
    return folder


def commit(folder, message):
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", message)
    return subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


class CheckoutTests(TestCase):
    def setUp(self):
        self.repo = repository()
        self.addCleanup(shutil.rmtree, self.repo)
        (self.repo / "model-a").mkdir()
        (self.repo / "model-a" / "reactions.py").write_text("one")
        (self.repo / "model-b").mkdir()
        (self.repo / "model-b" / "reactions.py").write_text("one")
        self.first = commit(self.repo, "first")
        (self.repo / "model-b" / "reactions.py").write_text("two")
        self.second = commit(self.repo, "second")

    def test_last_commit_that_changed_a_folder_or_file(self):
        checkout = Checkout(self.repo)
        self.assertEqual(checkout.commit(self.repo / "model-a"), self.first)
        self.assertEqual(checkout.commit(self.repo / "model-b"), self.second)
        self.assertEqual(checkout.commit(self.repo / "model-a" / "reactions.py"), self.first)

    def test_uncommitted_or_outside_gives_no_commit(self):
        (self.repo / "model-a" / "reactions.py").write_text("edited")
        (self.repo / "model-c").mkdir()
        (self.repo / "model-c" / "reactions.py").write_text("new")
        checkout = Checkout(self.repo)
        self.assertEqual(checkout.commit(self.repo / "model-a"), "")
        self.assertEqual(checkout.commit(self.repo / "model-c"), "")
        self.assertEqual(checkout.commit(self.repo / "model-b"), self.second)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        self.assertEqual(Checkout(outside).commit(outside), "")

    def test_github_address(self):
        self.assertEqual(github_blob("o/r", COMMIT, "a b/c.yaml"), f"https://github.com/o/r/blob/{COMMIT}/a%20b/c.yaml")
        self.assertEqual(github_blob("o/r", "", "a"), "")

    def test_importers_keep_the_commit_of_the_model_folder(self):
        model = db.KineticModel.objects.create(model_name="model-b")
        record_source_commits([(model, self.repo / "model-b")], MODELS)
        model.refresh_from_db()
        self.assertEqual(model.source_commit, self.second)
        (self.repo / "model-b" / "reactions.py").write_text("edited")
        record_source_commits([(model, self.repo / "model-b")], MODELS)
        model.refresh_from_db()
        self.assertEqual(model.source_commit, "")

    @override_settings(RMG_MODELS_GITHUB_REPO="comocheng/RMG-models")
    def test_model_links_to_its_libraries_at_the_commit(self):
        model = db.KineticModel(model_name="PCI2013/325-Husson", source_commit=COMMIT)
        self.assertEqual(model.kinetics_library_url, "https://github.com/comocheng/RMG-models/blob/"
                         f"{COMMIT}/PCI2013/325-Husson/RMG-Py-kinetics-library/reactions.py")
        self.assertEqual(db.KineticModel(model_name="x").thermo_library_url, "")

    def test_record_source_commits_fills_blank_commits(self):
        db.KineticModel.objects.create(model_name="model-a")
        db.KineticModel.objects.create(model_name="model-b", source_commit=COMMIT)
        db.KineticModel.objects.create(model_name="gone")
        out = StringIO()
        call_command("record_source_commits", "--rmg-models", str(self.repo), "--chemked", "", stdout=out)
        self.assertIn("set 1", out.getvalue())
        self.assertEqual(db.KineticModel.objects.get(model_name="model-a").source_commit, "")   # dry run
        call_command("record_source_commits", "--rmg-models", str(self.repo), "--chemked", "", "--apply",
                     stdout=StringIO())
        found = dict(db.KineticModel.objects.values_list("model_name", "source_commit"))
        self.assertEqual(found, {"model-a": self.first, "model-b": COMMIT, "gone": ""})
        call_command("record_source_commits", "--rmg-models", str(self.repo), "--chemked", "", "--apply", "--all",
                     stdout=StringIO())
        self.assertEqual(db.KineticModel.objects.get(model_name="model-b").source_commit, self.second)


class DatasetCommitTests(TestCase):
    def setUp(self):
        self.repo = repository()
        self.addCleanup(shutil.rmtree, self.repo)
        target = self.repo / IN_MAIN
        target.parent.mkdir(parents=True)
        shutil.copy(TESTDATA / "Test_2020_ST_7.yaml", target)
        self.commit = commit(self.repo, "a dataset")

    @override_settings(CHEMKED_GITHUB_REPO="pr-omethe-us/ChemKED-database")
    def test_sync_keeps_the_commit_of_the_file(self):
        call_command("sync_chemked", path=str(self.repo), stdout=StringIO(), stderr=StringIO())
        dataset = ExperimentDataset.objects.get(chemked_file_path=IN_MAIN)
        self.assertEqual(dataset.source_commit, self.commit)
        self.assertEqual(dataset.source_file_url,
                         f"https://github.com/pr-omethe-us/ChemKED-database/blob/{self.commit}/{IN_MAIN}")

    def test_web_upload_has_no_commit(self):
        import yaml
        data = yaml.safe_load((self.repo / IN_MAIN).read_text())
        store_chemked_data(data, "H2_upload", lambda message: None)
        self.assertEqual(ExperimentDataset.objects.get(chemked_file_path="H2_upload").source_commit, "")
        self.assertEqual(ExperimentDataset.objects.get(chemked_file_path="H2_upload").source_file_url, "")


@override_settings(RMG_MODELS_GITHUB_REPO="comocheng/RMG-models")
class SnapshotTests(TestCase):
    def setUp(self):
        self.h2 = species("H2", "InChI=1S/H2/h1H", "UFHFLCQGNIYNRP-UHFFFAOYSA-N-1")
        self.oh = species("OH", "InChI=1S/HO/h1H/u1", OH, multiplicity=2)
        self.h2o = species("H2O", "InChI=1S/H2O/h1H2", "XLYOFNOQVPJJNP-UHFFFAOYSA-N-1")
        self.h = species("H", "InChI=1S/H/u1", "YZCKVEUIGOORGS-UHFFFAOYSA-N-2", multiplicity=2)
        self.forward = reaction((-1, self.h2), (-1, self.oh), (1, self.h2o), (1, self.h))
        index_reactions(refresh=True)
        self.model = db.KineticModel.objects.get()
        db.KineticModel.objects.filter(pk=self.model.pk).update(source_commit=COMMIT)
        self.rate = db.Kinetics.objects.create(reaction=self.forward, raw_data=RATE)
        db.KineticsComment.objects.create(kinetics=self.rate, kinetic_model=self.model)
        self.thermo = db.Thermo.objects.create(species=self.oh, **POLY)
        db.ThermoComment.objects.create(thermo=self.thermo, kinetic_model=self.model)
        assign_all()

    def row(self, kind, record):
        return RecordKey.objects.get(kind=kind, object_id=record.pk, status="current")

    def test_key_keeps_the_values_and_the_models_with_their_commit(self):
        snapshot = self.row("kinetics", self.rate).snapshot
        self.assertEqual(snapshot["values"]["data"], RATE)
        self.assertEqual(snapshot["models"], [{"model": "Fixture/model one", "commit": COMMIT}])
        self.assertEqual(self.row("thermo", self.thermo).snapshot["values"]["coeffs_poly1"], POLY["coeffs_poly1"])
        self.assertIsNone(self.row("species", self.oh).snapshot)
        self.assertEqual(assign("kinetics", apply=True).snapshots, 0)      # nothing changed: nothing written

    def test_snapshot_follows_the_models_while_the_key_is_current(self):
        other = db.KineticModel.objects.create(model_name="Another model")
        db.KineticsComment.objects.create(kinetics=self.rate, kinetic_model=other)
        self.assertEqual(assign("kinetics", apply=True).snapshots, 1)
        models = [row["model"] for row in self.row("kinetics", self.rate).snapshot["models"]]
        self.assertEqual(models, ["Another model", "Fixture/model one"])

    def correct_the_rate(self):
        old = self.row("kinetics", self.rate).key
        self.rate.raw_data = {**RATE, "A": 2e14}
        self.rate.save()
        assign("kinetics", apply=True)
        return old, self.row("kinetics", self.rate).key

    def test_old_url_of_a_corrected_rate_shows_the_old_values(self):
        old, new = self.correct_the_rate()
        self.assertNotEqual(old, new)
        response = self.client.get(f"/id/kinetics/{old}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "These values were corrected")
        self.assertContains(response, f"/blob/{COMMIT}/Fixture/model%20one/RMG-Py-kinetics-library/reactions.py")
        self.assertIn(f"/id/kinetics/{new}>", response["Link"])
        data = self.client.get(f"/id/kinetics/{old}?format=json").json()
        self.assertEqual((data["status"], data["values"]["data"]["A"]), ("corrected", 1e14))
        self.assertTrue(data["current"].endswith(f"/id/kinetics/{new}"))
        self.assertEqual(self.client.get(f"/id/kinetics/{new}").status_code, 303)

    def test_a_second_correction_still_leads_to_the_current_record(self):
        first, second = self.correct_the_rate()
        self.rate.raw_data = {**RATE, "A": 3e14}
        self.rate.save()
        assign("kinetics", apply=True)
        third = self.row("kinetics", self.rate).key
        for old, value in ((first, 1e14), (second, 2e14)):
            data = self.client.get(f"/id/kinetics/{old}?format=json").json()
            self.assertEqual((data["values"]["data"]["A"], data["current"].rsplit("/id/kinetics/", 1)[1]),
                             (value, third))

    def test_new_identity_with_the_same_values_redirects(self):
        old = self.row("kinetics", self.rate).key
        db.Structure.objects.filter(isomer__species=self.oh).update(structure_key="NEWKEY-UHFFFAOYSA-N-2")
        index_reactions(refresh=True)
        assign_all()
        new = self.row("kinetics", self.rate).key
        self.assertNotEqual(old, new)
        response = self.client.get(f"/id/kinetics/{old}")
        self.assertEqual(response.status_code, 301)

    def test_removed_rate_shows_its_values_and_what_the_model_gives_now(self):
        old = self.row("kinetics", self.rate).key
        corrected = db.Kinetics.objects.create(reaction=self.forward, raw_data={**RATE, "A": 5e13})
        db.KineticsComment.objects.filter(kinetics=self.rate).update(kinetics=corrected)
        self.rate.delete()
        assign("kinetics", apply=True)
        response = self.client.get(f"/id/kinetics/{old}")
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "What these models give now", status_code=410)
        data = self.client.get(f"/id/kinetics/{old}?format=json").json()
        self.assertEqual(data["values"]["data"]["A"], 1e14)
        self.assertEqual([(row["model"], row["key"]) for row in data["now"]],
                         [("Fixture/model one", self.row("kinetics", corrected).key)])

    def test_old_url_of_corrected_thermo_shows_the_old_values(self):
        old = self.row("thermo", self.thermo).key
        db.Thermo.objects.filter(pk=self.thermo.pk).update(coeffs_poly1=[3.6, 0, 0, 0, 0, 100.0, 1.0])
        assign("thermo", apply=True)
        data = self.client.get(f"/id/thermo/{old}?format=json").json()
        self.assertEqual((data["status"], data["values"]["coeffs_poly1"][0]), ("corrected", 3.5))

    def test_api_gives_the_source_commit(self):
        self.assertEqual(self.client.get(f"/api/kineticmodel/{self.model.pk}/").json()["source_commit"], COMMIT)

    def drawable(self):
        """A rate and structures the record pages can draw (the key tests' fixture rate is only a
        value to hash, and their structures have no adjacency lists)."""
        db.Kinetics.objects.filter(pk=self.rate.pk).update(raw_data={
            "type": "arrhenius", "a": 1e14, "a_si": 1e8, "a_units": "cm^3/(mol*s)", "n": 0, "e": 0, "e_si": 0,
            "e_units": "kcal/mol"})
        for record, adjacency in (
                (self.h2, "1 H u0 p0 c0 {2,S}\n2 H u0 p0 c0 {1,S}"),
                (self.oh, "multiplicity 2\n1 O u1 p2 c0 {2,S}\n2 H u0 p0 c0 {1,S}"),
                (self.h2o, "1 O u0 p2 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}"),
                (self.h, "multiplicity 2\n1 H u1 p0 c0")):
            db.Structure.objects.filter(isomer__species=record).update(adjacency_list=adjacency)
        self.rate.refresh_from_db()
        assign("kinetics", apply=True)

    def test_record_page_lists_the_earlier_values(self):
        self.drawable()
        old = self.row("kinetics", self.rate).key
        self.rate.raw_data = {**self.rate.raw_data, "a": 2e14, "a_si": 2e8}
        self.rate.save()
        assign("kinetics", apply=True)
        response = self.client.get(f"/kinetics/{self.rate.pk}")
        self.assertContains(response, "Earlier values")
        self.assertContains(response, f"/id/kinetics/{old}")
        response = self.client.get(f"/id/kinetics/{old}")
        self.assertContains(response, "2e+14")                     # the current value, next to the old one
        self.assertContains(response, "1e+14")
        thermo_key = self.row("thermo", self.thermo).key
        db.Thermo.objects.filter(pk=self.thermo.pk).update(coeffs_poly1=[3.6, 0, 0, 0, 0, 100.0, 1.0])
        assign("thermo", apply=True)
        response = self.client.get(f"/thermo/{self.thermo.pk}")
        self.assertContains(response, "Earlier values")
        self.assertContains(response, f"/id/thermo/{thermo_key}")

    def test_record_page_links_to_the_source_file(self):
        self.drawable()
        response = self.client.get(f"/kinetics/{self.rate.pk}")
        self.assertContains(response, f"/blob/{COMMIT}/Fixture/model%20one/RMG-Py-kinetics-library/reactions.py")
        response = self.client.get(f"/thermo/{self.thermo.pk}")
        self.assertContains(response, f"/blob/{COMMIT}/Fixture/model%20one/RMG-Py-thermo-library/ThermoLibrary.py")

    def test_large_numbers_compare_equal_after_the_database(self):
        db.Kinetics.objects.filter(pk=self.rate.pk).update(raw_data={**RATE, "A": 1.233e66})
        assign("kinetics", apply=True)
        self.assertEqual(assign("kinetics", apply=True).snapshots, 0)
        response = self.client.get(f"/id/kinetics/{self.row('kinetics', self.rate).key}")
        self.assertEqual(response.status_code, 303)
