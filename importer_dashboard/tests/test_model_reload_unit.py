"""
A push to RMG-models that changes a model's files reloads that model into the database
(importer_dashboard/model_reload.py): applied when its libraries load and every entry imports,
held for Apply on the Settings page otherwise.

The model is a small one written here in RMG's library format (made-up thermo for H, O2, O and
OH and one rate), in a git repository that stands for the read copy.
"""
import os
import subprocess
import tempfile
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from database import models as db
from importer_dashboard import model_reload, read_copy_sync
from importer_dashboard.models import ModelReload

SPECIES = {
    "H": "multiplicity 2\n1 H u1 p0 c0",
    "O2": "multiplicity 3\n1 O u1 p2 c0 {2,S}\n2 O u1 p2 c0 {1,S}",
    "O": "multiplicity 3\n1 O u2 p2 c0",
    "OH": "multiplicity 2\n1 O u1 p2 c0 {2,S}\n2 H u0 p0 c0 {1,S}",
}
SMILES = "H\t[H]\nO2\t[O][O]\nO\t[O]\nOH\t[OH]\n"


def thermo_library(first_oh=3.6):
    entries = []
    for index, (label, adjacency) in enumerate(SPECIES.items()):
        a0 = first_oh if label == "OH" else 2.5 + index / 10
        entries.append(f'''entry(
    index = {index},
    label = "{label}",
    molecule =
"""
{adjacency}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[{a0},0.001,0,0,0,{1000 * (index + 1)},1.0], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[{a0},0.001,0,0,0,{1000 * (index + 1)},1.0], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """test""",
)
''')
    return 'name = "Tiny"\nshortDesc = "test"\nlongDesc = """test"""\n' + "\n".join(entries)


KINETICS = '''name = "Tiny"
shortDesc = "test"
longDesc = """test"""
entry(
    index = 0,
    label = "H + O2 <=> O + OH",
    degeneracy = 1.0,
    kinetics = Arrhenius(A=(1.04e+14,'cm^3/(mol*s)'), n=0, Ea=(15286,'cal/mol'), T0=(1,'K')),
    shortDesc = """test""",
)
'''
DICTIONARY = "\n\n".join(f"{label}\n{adjacency}" for label, adjacency in SPECIES.items()) + "\n"


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout.strip()


class ModelReloadTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "RMG-models")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "master")
        git(self.repo, "config", "user.email", "test@example.org")
        git(self.repo, "config", "user.name", "Test")
        self.write(thermo_library(), KINETICS, SMILES)
        self.write_file("Other/SMILES.txt", "H\t[H]\n")
        self.first = self.commit("Tiny model")
        settings = override_settings(RMG_MODELS_PATH=self.repo, RMG_MODELS_AUTO_RELOAD=True)
        settings.enable()
        self.addCleanup(settings.disable)
        call_command("import_rmg_models", model="Tiny", path=self.repo, stdout=StringIO(), stderr=StringIO())
        self.model = db.KineticModel.objects.get(model_name="Tiny")

    def write_file(self, name, text):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def write(self, thermo=None, kinetics=None, smiles=None):
        if thermo is not None:
            self.write_file("Tiny/RMG-Py-thermo-library/ThermoLibrary.py", thermo)
        if kinetics is not None:
            self.write_file("Tiny/RMG-Py-kinetics-library/reactions.py", kinetics)
            self.write_file("Tiny/RMG-Py-kinetics-library/dictionary.txt", DICTIONARY)
        if smiles is not None:
            self.write_file("Tiny/SMILES.txt", smiles)
            self.write_file("Tiny/source.txt", "Test, A. (2026). A tiny model. J. Test 1, 1.\n")

    def commit(self, message):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def oh_thermo(self):
        return db.Thermo.objects.get(thermocomment__kinetic_model=self.model,
                                     species__speciesname__name="OH", species__speciesname__kinetic_model=self.model)

    def test_the_import_reads_the_tiny_model(self):
        self.assertEqual(self.oh_thermo().coeffs_poly1[0], 3.6)
        self.assertEqual(db.KineticsComment.objects.filter(kinetic_model=self.model).count(), 1)

    def test_a_changed_library_is_reloaded_and_the_keys_follow(self):
        call_command("assign_record_keys", "--apply", stdout=StringIO())
        self.write(thermo=thermo_library(first_oh=3.7))
        second = self.commit("Corrected the OH thermo")
        [record] = model_reload.reload_changed(self.first, second)
        self.assertEqual((record.model_name, record.status), ("Tiny", ModelReload.Status.APPLIED))
        self.assertEqual(record.files, ["Tiny/RMG-Py-thermo-library/ThermoLibrary.py"])
        self.assertEqual(self.oh_thermo().coeffs_poly1[0], 3.7)
        self.model.refresh_from_db()
        self.assertEqual(self.model.source_commit, second)
        # The importer made a new thermo row for the new values; the old row stays, with no model,
        # so its canonical URL still gives the old values.
        from provenance.models import RecordKey
        old_rows = db.Thermo.objects.filter(coeffs_poly1__0=3.6, species=self.oh_thermo().species)
        self.assertEqual(old_rows.count(), 1)
        self.assertFalse(old_rows[0].thermocomment_set.exists())
        key = RecordKey.objects.get(kind="thermo", object_id=old_rows[0].pk, status="current")
        self.assertEqual((key.snapshot["values"]["coeffs_poly1"][0], key.snapshot["models"]), (3.6, []))

    def test_only_models_whose_folders_changed_are_reloaded(self):
        db.KineticModel.objects.create(model_name="Other")
        self.write_file("Other/SMILES.txt", "H\t[H]\nO\t[O]\n")
        second = self.commit("Other model only")
        records = model_reload.reload_changed(self.first, second)
        self.assertEqual([r.model_name for r in records], ["Other"])
        self.assertEqual(records[0].status, ModelReload.Status.FAILED)          # it has no library
        self.assertIn("No RMG-Py library", records[0].message)

    def test_a_library_that_does_not_load_is_held_and_apply_keeps_the_old_links(self):
        self.write(thermo="this is not a library (")
        second = self.commit("Broke the thermo library")
        [record] = model_reload.reload_changed(self.first, second)
        self.assertEqual(record.status, ModelReload.Status.HELD)
        self.assertIn("thermo library: library not loaded", record.message)
        self.assertEqual(self.oh_thermo().coeffs_poly1[0], 3.6)                # rolled back
        model_reload.reload(record, force=True)
        self.assertEqual(record.status, ModelReload.Status.APPLIED)
        self.assertEqual(self.oh_thermo().coeffs_poly1[0], 3.6)                # the old link is kept

    def test_smiles_without_regenerated_libraries_says_so(self):
        self.write(smiles=SMILES + "# a note\n")
        second = self.commit("SMILES only")
        [record] = model_reload.reload_changed(self.first, second)
        self.assertEqual(record.status, ModelReload.Status.APPLIED)
        self.assertIn("regenerate them", record.message)

    def test_off_reloads_nothing(self):
        self.write(thermo=thermo_library(first_oh=3.7))
        second = self.commit("Corrected the OH thermo")
        with override_settings(RMG_MODELS_AUTO_RELOAD=False):
            self.assertEqual(model_reload.reload_changed(self.first, second), [])
        self.assertEqual(self.oh_thermo().coeffs_poly1[0], 3.6)


class SyncQueuesTheReloadTests(TestCase):
    @override_settings(RMG_MODELS_AUTO_RELOAD=True)
    def test_a_fast_forward_queues_the_reload_of_the_changed_models(self):
        with patch.object(read_copy_sync, "is_git_repository", return_value=True), \
                patch.object(read_copy_sync, "_fast_forward", return_value=("updated", "Moved.", "a" * 40, "b" * 40)), \
                patch.object(read_copy_sync, "_add_new_models", return_value=[]), \
                patch.object(read_copy_sync, "_save_status"), \
                patch("importer_dashboard.tasks.reload_changed_models.delay") as delay, \
                patch("importer_dashboard.tasks.schedule_evidence_index_refresh"):
            read_copy_sync.sync("webhook")
        delay.assert_called_once_with("a" * 40, "b" * 40)

    def test_no_queue_when_off(self):
        with override_settings(RMG_MODELS_AUTO_RELOAD=False), \
                patch.object(read_copy_sync, "is_git_repository", return_value=True), \
                patch.object(read_copy_sync, "_fast_forward", return_value=("updated", "Moved.", "a" * 40, "b" * 40)), \
                patch.object(read_copy_sync, "_add_new_models", return_value=[]), \
                patch.object(read_copy_sync, "_save_status"), \
                patch("importer_dashboard.tasks.reload_changed_models.delay") as delay, \
                patch("importer_dashboard.tasks.schedule_evidence_index_refresh"):
            read_copy_sync.sync("webhook")
        delay.assert_not_called()


class SettingsPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.org", "x")
        self.held = ModelReload.objects.create(model_name="Tiny", old_commit="a" * 40, new_commit="b" * 40,
                                               status=ModelReload.Status.HELD, message="Held: thermo library: test.")
        self.client.force_login(self.admin)

    def test_settings_lists_reloads_with_apply_for_held_ones(self):
        response = self.client.get(reverse("importer_dashboard:settings"))
        self.assertContains(response, "Models reloaded into the database")
        self.assertContains(response, "Held: thermo library: test.")
        self.assertContains(response, reverse("importer_dashboard:model_reload_apply", args=[self.held.pk]))

    def test_apply_queues_the_held_reload(self):
        with patch("importer_dashboard.tasks.apply_model_reload.delay") as delay:
            self.client.post(reverse("importer_dashboard:model_reload_apply", args=[self.held.pk]))
        delay.assert_called_once_with(self.held.pk, self.admin.pk)

    def test_only_a_held_reload_can_be_applied(self):
        self.held.status = ModelReload.Status.APPLIED
        self.held.save()
        with patch("importer_dashboard.tasks.apply_model_reload.delay") as delay:
            self.client.post(reverse("importer_dashboard:model_reload_apply", args=[self.held.pk]))
        delay.assert_not_called()
