"""Filters of the record endpoints (species, reaction, kinetics, thermo), fields on the model list,
the documented rate fingerprint, and the licence and identifier of the datasets."""
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from chemked_database.models import ExperimentDataset
from database import models as db
from database.tests.test_database_cleanup import FIELDS, RATE, provider_copy, reaction


def species(name, inchi, multiplicity=1, **fields):
    formula, _ = db.Formula.objects.get_or_create(formula=inchi.split("/")[1])
    isomer, _ = db.Isomer.objects.get_or_create(formula=formula, inchi=inchi)
    record = db.Species.objects.create(hash=name, **fields)
    record.isomers.add(isomer)
    db.Structure.objects.get_or_create(isomer=isomer, multiplicity=multiplicity,
                                       defaults={"smiles": name, "adjacency_list": f"fixture {name}"})
    return record


class RecordFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.o2 = species("O2", "InChI=1S/O2/c1-2/u1,2", multiplicity=3)
        cls.o2x = species("O2X", "InChI=1S/O2/c1-2")
        cls.oh = species("OH", "InChI=1S/HO/h1H/u1", multiplicity=2)
        cls.ohx = species("OHX", "InChI=1S/HO/h1H/u1", multiplicity=2, electronic_state="excited")
        cls.h = species("H", "InChI=1S/H/u1", multiplicity=2)
        cls.h2 = species("H2", "InChI=1S/H2/h1H")
        cls.h2o = species("H2O", "InChI=1S/H2O/h1H2")
        cls.forward = reaction((-1, cls.h2), (-1, cls.oh), (1, cls.h2o), (1, cls.h))
        cls.backward = reaction((-1, cls.h), (-1, cls.h2o), (1, cls.h2), (1, cls.oh))
        cls.other = reaction((-1, cls.h), (-1, cls.o2), (1, cls.oh))
        db.Reaction.objects.filter(pk__in=[cls.forward.pk, cls.backward.pk]).update(canonical_key="K1", layer="H2/O2")
        db.Reaction.objects.filter(pk=cls.other.pk).update(canonical_key="K2", layer="H2/O2")
        cls.k_forward = db.Kinetics.objects.create(reaction=cls.forward, raw_data=RATE)
        cls.k_backward = db.Kinetics.objects.create(reaction=cls.backward, raw_data=RATE)
        cls.k_other = db.Kinetics.objects.create(reaction=cls.other, raw_data=RATE)
        cls.m1 = db.KineticModel.objects.create(model_name="Model one")
        cls.m2 = db.KineticModel.objects.create(model_name="Model two")
        db.KineticsComment.objects.create(kinetic_model=cls.m1, kinetics=cls.k_forward)
        db.KineticsComment.objects.create(kinetic_model=cls.m2, kinetics=cls.k_backward)
        db.KineticsComment.objects.create(kinetic_model=cls.m2, kinetics=cls.k_other)
        db.SpeciesName.objects.create(kinetic_model=cls.m1, species=cls.o2, name="O2")
        cls.t_model = db.Thermo.objects.create(species=cls.o2, **FIELDS)
        db.ThermoComment.objects.create(kinetic_model=cls.m1, thermo=cls.t_model)
        cls.t_reference = provider_copy(cls.o2)

    def ids(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return {row["id"] for row in response.json()["results"]}

    def test_species_by_exact_inchi(self):
        both = {self.o2.pk, self.o2x.pk}
        self.assertEqual(self.ids("/api/species/?inchi=1S/O2/c1-2"), both)
        self.assertEqual(self.ids("/api/species/?inchi=InChI=1S/O2/c1-2"), both)
        self.assertEqual(self.ids("/api/species/?inchi=1S/O2/c1-2/u1,2"), {self.o2.pk})
        self.assertEqual(self.ids("/api/species/?inchi=1S/O2/c1-2&multiplicity=3"), {self.o2.pk})
        # search is a substring match; inchi is exact
        self.assertEqual(self.ids("/api/species/?inchi=1S/H"), {self.h.pk})
        self.assertTrue({self.h2.pk, self.oh.pk} <= self.ids("/api/species/?search=1S/H"))

    def test_species_by_electronic_state_and_model(self):
        self.assertEqual(self.ids("/api/species/?inchi=1S/HO/h1H&has_electronic_state=false"), {self.oh.pk})
        self.assertEqual(self.ids("/api/species/?inchi=1S/HO/h1H&has_electronic_state=true"), {self.ohx.pk})
        self.assertEqual(self.ids(f"/api/species/?kinetic_model={self.m1.pk}"), {self.o2.pk})

    def test_reactions_by_species_model_and_canonical_key(self):
        four = f"species={self.h2.pk}&species={self.oh.pk}&species={self.h2o.pk}&species={self.h.pk}"
        self.assertEqual(self.ids(f"/api/reaction/?{four}"), {self.forward.pk, self.backward.pk})
        self.assertEqual(self.ids("/api/reaction/?canonical_key=K1"), {self.forward.pk, self.backward.pk})
        self.assertEqual(self.ids(f"/api/reaction/?kinetic_model={self.m2.pk}"), {self.backward.pk, self.other.pk})

    def test_kinetics_by_reaction_model_species_and_canonical_key(self):
        self.assertEqual(self.ids("/api/kinetics/?canonical_key=K1"), {self.k_forward.pk, self.k_backward.pk})
        self.assertEqual(self.ids(f"/api/kinetics/?reaction={self.forward.pk}"), {self.k_forward.pk})
        self.assertEqual(self.ids(f"/api/kinetics/?kinetic_model={self.m1.pk}"), {self.k_forward.pk})
        self.assertEqual(self.ids(f"/api/kinetics/?species={self.o2.pk}"), {self.k_other.pk})
        self.assertEqual(self.ids(f"/api/kinetics/?id__in={self.k_forward.pk},{self.k_other.pk}"),
                         {self.k_forward.pk, self.k_other.pk})

    def test_thermo_by_species_model_and_reference(self):
        both = {self.t_model.pk, self.t_reference.pk}
        self.assertEqual(self.ids(f"/api/thermo/?species={self.o2.pk}"), both)
        self.assertEqual(self.ids(f"/api/thermo/?species={self.o2.pk}&reference=false"), {self.t_model.pk})
        self.assertEqual(self.ids(f"/api/thermo/?species={self.o2.pk}&reference=true"), {self.t_reference.pk})
        self.assertEqual(self.ids(f"/api/thermo/?kinetic_model={self.m1.pk}"), {self.t_model.pk})

    def test_unknown_parameters_are_still_refused(self):
        self.assertEqual(self.client.get("/api/thermo/?foo=1").status_code, 400)

    def test_model_list_takes_fields_and_omit(self):
        row = self.client.get("/api/kineticmodel/?fields=id,model_name").json()["results"][0]
        self.assertEqual(set(row), {"id", "model_name"})
        row = self.client.get("/api/kineticmodel/?omit=speciesname_set,kineticscomment_set").json()["results"][0]
        self.assertNotIn("speciesname_set", row)
        self.assertIn("thermocomment_set", row)

    def test_rate_fingerprint_is_described_in_the_schema(self):
        schema = self.client.get("/api/schema/").content.decode()
        self.assertIn("log10 of the rate coefficient in SI units", schema)


class DatasetLicenceTests(TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        (self.repo / "CITATION.cff").write_text("cff-version: 1.2.0\ntitle: x\nlicense: CC-BY-4.0\n")
        self.dataset = ExperimentDataset.objects.create(
            chemked_file_path="test/a.yaml", experiment_type="ignition delay", reference_doi="10.1000/paper")

    def test_dry_run_then_apply(self):
        call_command("backfill_dataset_licences", "--path", str(self.repo), stdout=open("/dev/null", "w"))
        self.dataset.refresh_from_db()
        self.assertIsNone(self.dataset.license)
        call_command("backfill_dataset_licences", "--path", str(self.repo), "--apply", stdout=open("/dev/null", "w"))
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.license.spdx_id, "CC-BY-4.0")

    def test_json_ld_identifier_is_the_dataset_and_the_paper_is_the_citation(self):
        data = self.client.get(f"/api/experiment-dataset/{self.dataset.pk}/metadata/").json()
        self.assertTrue(data["schema:identifier"].endswith(f"/api/experiment-dataset/{self.dataset.pk}/"))
        self.assertEqual(data["schema:citation"], "https://doi.org/10.1000/paper")
