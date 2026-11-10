"""Collider efficiencies belong to the rate record. PCI2017/024-Bohon writes H2O2 (+M) <=> 2 OH
with the parameters of other models but H2O 0.0, because H2O has its own (+H2O) rate; it must
not be linked to a record with another model's H2O 7.5. Here: H + O2 (+M) <=> HO2 (+M)."""
import importlib
import re
import shutil
import tempfile
from types import SimpleNamespace

from django.apps import apps
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from database import models as db
from database.models.kinetic_data import efficiencies_hash
from database.scripts.import_rmg_models import get_or_create_species, import_kinetics, import_thermo
from database.services import cleanup, exports
from database.tests.test_database_cleanup import reaction, split_records
from database.tests.test_import_rmg_species_unit import MODELS, molecule
from database.tests.test_specific_collider_unit import KONNOV, collider_model, import_model

RATE = KONNOV["H + O2 <=> HO2"][:3]


def library(efficiencies):
    return {"H + O2 <=> HO2": (*RATE, efficiencies)}


FIRST = library("{'O': 10.0, '[Ar]': 0.7}")
OWN = library("{'O': 0.0, '[Ar]': 0.7}")
FIRST_REORDERED = library("{'[Ar]': 0.7, 'O': 10.0}")
NONE = library("{}")


def record(model):
    (kinetics,) = db.Kinetics.objects.filter(kineticscomment__kinetic_model=model)
    return kinetics


def efficiencies(model):
    """Collider label -> efficiency of the model's rate record."""
    names = dict(db.SpeciesName.objects.filter(kinetic_model=model).values_list("species_id", "name"))
    return {names[e.species_id]: e.efficiency for e in record(model).efficiency_set.all()}


def stored_hash(kinetics):
    return efficiencies_hash(kinetics.efficiency_set.values_list("species_id", "efficiency"))


class ColliderEfficienciesImportTests(TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.first, *_ = import_model(self.directory, "first", FIRST)

    def test_other_efficiencies_get_their_own_record(self):
        own, _, _, counts = import_model(self.directory, "own", OWN)
        self.assertEqual((counts["imported"], counts["failed"]), (1, 0))
        self.assertNotEqual(record(own).pk, record(self.first).pk)
        self.assertEqual(record(own).raw_data, record(self.first).raw_data)
        self.assertEqual(efficiencies(self.first), {"H2O": 10.0, "AR": 0.7})
        self.assertEqual(efficiencies(own), {"H2O": 0.0, "AR": 0.7})

    def test_the_same_efficiencies_share_the_record(self):
        same, *_ = import_model(self.directory, "same", FIRST_REORDERED)
        self.assertEqual(record(same).pk, record(self.first).pk)
        self.assertEqual(db.Efficiency.objects.count(), 2)
        self.assertEqual(efficiencies(same), {"H2O": 10.0, "AR": 0.7})

    def test_no_efficiencies_is_another_record(self):
        none, *_ = import_model(self.directory, "none", NONE)
        self.assertNotEqual(record(none).pk, record(self.first).pk)
        self.assertEqual((record(none).efficiencies_hash, efficiencies(none)), ("", {}))

    def test_importing_again_finds_the_same_records(self):
        own, _, own_path, _ = import_model(self.directory, "own", OWN)
        before = sorted(db.Efficiency.objects.values_list("kinetics_id", "species_id", "efficiency"))
        counts = import_kinetics(own_path, own, MODELS)
        self.assertEqual((counts["imported"], counts["failed"]), (1, 0))
        self.assertEqual(sorted(db.Efficiency.objects.values_list("kinetics_id", "species_id", "efficiency")), before)
        self.assertEqual(db.Kinetics.objects.count(), 2)

    def test_hash_is_that_of_the_rows_and_the_migration_gives_it_too(self):
        own, *_ = import_model(self.directory, "own", OWN)
        hashes = {k.pk: k.efficiencies_hash for k in db.Kinetics.objects.all()}
        self.assertEqual(hashes, {k.pk: stored_hash(k) for k in db.Kinetics.objects.all()})
        self.assertEqual(len(set(hashes.values())), 2)
        migration = importlib.import_module("database.migrations.0017_kinetics_efficiencies_hash")
        for pk in hashes:
            db.Kinetics.objects.filter(pk=pk).update(efficiencies_hash=f"before {pk}")
        migration.fill_efficiencies_hash(apps, None)
        self.assertEqual(dict(db.Kinetics.objects.values_list("pk", "efficiencies_hash")), hashes)
        self.assertEqual(cleanup.integrity_report()["kinetics_with_stale_efficiencies_hash"], 0)

    def test_api_gives_each_models_efficiencies(self):
        own, *_ = import_model(self.directory, "own", OWN)
        for model, h2o in ((self.first, 10.0), (own, 0.0)):
            data = self.client.get(f"/api/kinetics/{record(model).pk}/").json()
            water = db.SpeciesName.objects.get(kinetic_model=model, name="H2O").species_id
            self.assertEqual({e["species"]: e["efficiency"] for e in data["efficiency_set"]}[water], h2o)
            self.assertNotIn("efficiencies_hash", data)

    def test_cantera_file_has_each_models_efficiencies(self):
        import cantera as ct
        own, *_ = import_model(self.directory, "own", OWN)
        for model, h2o in ((self.first, 10.0), (own, 0.0)):
            solution = ct.Solution(yaml=exports.build_cantera_yaml(model).content.decode())
            (rate,) = [r for r in solution.reactions() if "HO2" in r.equation]
            water = next(name for name in rate.third_body.efficiencies if name.startswith("H2O"))
            self.assertEqual(rate.third_body.efficiencies[water], h2o)


class ColliderEfficienciesRebuildTests(TestCase):
    """A model imported before efficiencies were part of the identity, rebuilt."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.first, *_ = import_model(self.directory, "first", FIRST)
        self.own, self.thermo_path, self.kinetics_path, _ = import_model(self.directory, "own", OWN)
        # What the older import left: the model linked to the first model's record.
        self.shared = record(self.first)
        own_rate = record(self.own)
        db.KineticsComment.objects.filter(kinetics=own_rate).update(kinetics=self.shared)
        own_rate.delete()

    def test_rebuild_links_a_record_with_the_models_efficiencies(self):
        self.assertEqual(efficiencies(self.own), {"H2O": 10.0, "AR": 0.7})
        result = cleanup.rebuild_model_links(self.own, self.thermo_path, self.kinetics_path)
        self.assertEqual((result["kinetics_links"]["removed"], result["kinetics_links"]["added"]), (1, 1))
        self.assertEqual(efficiencies(self.own), {"H2O": 0.0, "AR": 0.7})
        self.assertEqual(record(self.own).raw_data, self.shared.raw_data)
        # The first model keeps its record.
        self.assertEqual((record(self.first), efficiencies(self.first)), (self.shared, {"H2O": 10.0, "AR": 0.7}))

    def test_record_that_no_model_has_any_more_is_pruned(self):
        cleanup.rebuild_model_links(self.own, self.thermo_path, self.kinetics_path)
        # The first library was corrected since its import (as CO was, from triplet to singlet).
        corrected = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, corrected)
        thermo_path, kinetics_path = collider_model(corrected, "first", OWN)
        cleanup.rebuild_model_links(self.first, thermo_path, kinetics_path)
        self.assertEqual(record(self.first), record(self.own))
        self.assertEqual(cleanup.prune_unlinked_rows(apply=True)["database.Kinetics"]["deleted"], 1)
        self.assertFalse(db.Kinetics.objects.filter(pk=self.shared.pk).exists())
        self.assertFalse(db.Efficiency.objects.filter(kinetics_id=self.shared.pk).exists())


class ColliderEfficienciesMergeTests(TestCase):
    """Two records of one rate whose colliders are two records of one species."""

    def setUp(self):
        single, self.full = split_records()
        h, o2, ho2 = (get_or_create_species(None, "", [molecule(label)], MODELS) for label in ("H", "O2", "HO2"))
        rate = {"type": "arrhenius", "a": 1e14, "n": 0, "e": 0}
        self.reaction = reaction((-1, h), (-1, o2), (1, ho2))
        self.kinetics = []
        for name, collider in (("a", single), ("b", self.full)):
            kinetics = db.Kinetics.objects.create(reaction=self.reaction, raw_data=rate)
            db.Efficiency.objects.create(kinetics=kinetics, species=collider, efficiency=2.0)
            kinetics.refresh_efficiencies_hash()
            model = db.KineticModel.objects.create(model_name=name)
            db.KineticsComment.objects.create(kinetics=kinetics, kinetic_model=model)
            self.kinetics.append(kinetics)

    def test_merging_the_species_merges_the_rates(self):
        report = cleanup.merge_split_species(apply=True)
        self.assertEqual(report["kinetics_merged"], 1)
        (kinetics,) = db.Kinetics.objects.filter(reaction=self.reaction)
        self.assertEqual(list(kinetics.efficiency_set.values_list("species_id", "efficiency")), [(self.full.pk, 2.0)])
        self.assertEqual(kinetics.efficiencies_hash, stored_hash(kinetics))
        self.assertEqual(set(kinetics.kineticscomment_set.values_list("kinetic_model__model_name", flat=True)),
                         {"a", "b"})
        self.assertEqual(cleanup.integrity_report()["kinetics_with_stale_efficiencies_hash"], 0)

    def test_report_counts_a_stale_hash(self):
        db.Efficiency.objects.filter(kinetics=self.kinetics[0]).update(efficiency=3.0)
        self.assertEqual(cleanup.integrity_report()["kinetics_with_stale_efficiencies_hash"], 1)


class ColliderEfficiencyEditTests(TestCase):
    """Edits in the admin and through the API keep the fingerprint current."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.model, *_ = import_model(self.directory, "first", FIRST)
        self.kinetics = record(self.model)
        self.request = RequestFactory().post("/")
        self.request.user = get_user_model().objects.create_superuser("admin", "admin@example.org", "pw")

    def test_admin_edits_refresh_the_hash(self):
        efficiency_admin = site._registry[db.Efficiency]
        row = self.kinetics.efficiency_set.first()
        row.efficiency = 0.0
        efficiency_admin.save_model(self.request, row, None, True)
        self.kinetics.refresh_from_db()
        self.assertEqual(self.kinetics.efficiencies_hash, stored_hash(self.kinetics))
        efficiency_admin.delete_model(self.request, row)
        self.kinetics.refresh_from_db()
        self.assertEqual(self.kinetics.efficiencies_hash, stored_hash(self.kinetics))
        # The rate's own page: the inline rows are saved, then the hash.
        db.Efficiency.objects.filter(kinetics=self.kinetics).delete()
        form = SimpleNamespace(instance=self.kinetics, save_m2m=lambda: None)
        site._registry[db.Kinetics].save_related(self.request, form, [], True)
        self.kinetics.refresh_from_db()
        self.assertEqual(self.kinetics.efficiencies_hash, "")

    def test_api_update_refreshes_the_hash(self):
        client = APIClient()
        client.force_authenticate(self.request.user)
        data = client.get(f"/api/kinetics/{self.kinetics.pk}/").json()
        data["efficiency_set"] = [{"species": e["species"], "efficiency": 1.0} for e in data["efficiency_set"]]
        response = client.put(f"/api/kinetics/{self.kinetics.pk}/", data, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.kinetics.refresh_from_db()
        self.assertEqual(set(self.kinetics.efficiency_set.values_list("efficiency", flat=True)), {1.0})
        self.assertEqual(self.kinetics.efficiencies_hash, stored_hash(self.kinetics))


def third_body_model(root, name, efficiencies):
    """H + O2 + M <=> HO2 + M as a three-body rate (GRI-Mech 3.0 writes it so), not a falloff one."""
    thermo_path, kinetics_path = collider_model(root, name, {})
    with open(kinetics_path, "a") as handle:
        handle.write(f'''
entry(
    index = 0,
    label = "H + O2 <=> HO2",
    degeneracy = 1.0,
    kinetics = ThirdBody(arrheniusLow=Arrhenius(A=(2.8e+18,'cm^6/(mol^2*s)'), n=-0.86, Ea=(0,'cal/mol'), T0=(1,'K')), efficiencies={efficiencies}),
    shortDesc = """The chemkin file reaction is H + O2 + M <=> HO2 + M""",
)
''')
    return thermo_path, kinetics_path


class ThirdBodyEfficiencyExportTests(TestCase):
    """A three-body rate keeps its collider efficiencies in the RMG object and the exports."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.model = db.KineticModel.objects.create(model_name="gri")
        thermo_path, kinetics_path = third_body_model(self.directory, "gri", "{'O': 10.0, '[Ar]': 0.38, '[O][O]': 0.0}")
        import_thermo(thermo_path, self.model, MODELS)
        import_kinetics(kinetics_path, self.model, MODELS)
        self.rate = record(self.model)

    def test_rmg_kinetics_have_the_efficiencies(self):
        self.assertEqual(self.rate.raw_data["type"], "third_body")
        self.assertEqual(efficiencies(self.model), {"H2O": 10.0, "AR": 0.38, "O2": 0.0})
        for rmg_kinetics in (self.rate.to_rmg().kinetics, self.rate.rmg_kinetics()):
            self.assertEqual(sorted(rmg_kinetics.efficiencies.values()), [0.0, 0.38, 10.0])

    def test_chemkin_file_has_the_efficiencies(self):
        (text,) = [v.decode() for k, v in exports._generate_chemkin_files(self.model).items() if k.endswith("_chem.inp")]
        lines = text.splitlines()
        (index,) = [i for i, line in enumerate(lines) if "+M" in line.replace(" ", "") and "HO2" in line]
        written = dict(re.findall(r"([A-Z0-9]+)(?:\(\d+\))?/\s*([\d.]+)/", lines[index + 1]))
        self.assertEqual({k: float(v) for k, v in written.items()}, {"H2O": 10.0, "AR": 0.38, "O2": 0.0})

    def test_cantera_file_has_the_efficiencies(self):
        import cantera as ct
        solution = ct.Solution(yaml=exports.build_cantera_yaml(self.model).content.decode())
        (rate,) = [r for r in solution.reactions() if "HO2" in r.equation]
        self.assertEqual(rate.reaction_type, "three-body-Arrhenius")
        written = {re.sub(r"\(\d+\)$", "", name): value for name, value in rate.third_body.efficiencies.items()}
        self.assertEqual(written, {"H2O": 10.0, "AR": 0.38, "O2": 0.0})
