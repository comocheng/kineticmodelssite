"""The REST API and the pages show speciation measurements with their profiles."""

import io
import shutil
import tempfile
from pathlib import Path

import yaml
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import ExperimentDataset
from .speciation import stored_rows
from .test_export import FLAME_FILE, JSR_FILE


class SpeciationViewTests(TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        for rel, text in (("x/flame.yaml", FLAME_FILE), ("x/jsr.yaml", JSR_FILE)):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        call_command(
            "sync_chemked", path=str(root), files=["x/flame.yaml", "x/jsr.yaml"],
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        self.flame = ExperimentDataset.objects.get(chemked_file_path="x/flame.yaml")
        self.jsr = ExperimentDataset.objects.get(chemked_file_path="x/jsr.yaml")

    def _api(self, path, **params):
        response = self.client.get(path, params, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content[:300])
        return response.json()["results"]

    def test_api_gives_measurements_with_their_profiles(self):
        source = yaml.safe_load(FLAME_FILE)["datapoints"][0]

        (item,) = self._api(
            "/api/speciation-measurement/",
            datapoint__dataset__apparatus__kind="burner stabilized flame",
        )

        self.assertEqual(item["datapoint"], self.flame.datapoints.get().pk)
        self.assertEqual(
            [(v["column"], v["name"], v["units"]) for v in item["independent_variables"]],
            [(0, "distance", "mm")],
        )
        (profile,) = item["concentration_profiles"]
        self.assertEqual(profile["species"]["species_name"], "NO")
        self.assertEqual(profile["values"], source["concentration-profiles"][0]["values"])
        self.assertEqual(profile["evaluated_standard_deviation_method"], "statistical scatter")
        self.assertEqual(item["auxiliary_profiles"][0]["profile_type"], "temperature")
        self.assertEqual(item["flow_rate_quantity"]["units"], "kg * m**-2 * s**-1")

    def test_api_filters_by_measured_species(self):
        (profile,) = self._api("/api/concentration-profile/", species__species_name="CH2O")
        self.assertEqual(profile["quantity_units"], "ppm")
        self.assertEqual(profile["uncertainty_sourcetype"], "reported")

        # Both JSR datapoints measured NC5H12; each is listed once
        items = self._api(
            "/api/speciation-measurement/", concentration_profiles__species__species_name="NC5H12"
        )
        self.assertEqual(len(items), 2)

    def test_old_speciation_endpoints_are_gone(self):
        for path in ("/api/jet-stirred-reactor/", "/api/burner-stabilized-flame/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_dataset_page_shows_profiles(self):
        response = self.client.get(reverse("chemked_database:dataset-detail", args=[self.jsr.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Species Profiles")
        self.assertContains(response, 'id="speciation-chart-data"')
        self.assertContains(response, "NC5H12, CH2O")
        self.assertContains(response, "reactor-volume")

    def test_datapoint_page_shows_profiles(self):
        datapoint = self.flame.datapoints.get()

        response = self.client.get(reverse("chemked_database:datapoint-detail", args=[datapoint.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Concentration Profiles (1)")
        self.assertContains(response, "Auxiliary Profiles (1)")
        self.assertContains(response, "1S/NO/c1-2")
        self.assertContains(response, "Flow rate")

    def test_species_page_lists_datapoints_that_measured_it(self):
        response = self.client.get(reverse("chemked_database:species-datapoints", args=["CH2O"]))

        self.assertEqual(response.status_code, 200)
        datapoint = self.jsr.datapoints.order_by("pk").first()
        self.assertContains(response, reverse("chemked_database:datapoint-detail", args=[datapoint.pk]))


class StoredRowsTests(SimpleTestCase):
    def test_floats_rewritten_by_jsonb_are_floats_again(self):
        # ReSpecTh's missing-value marker, as PostgreSQL's jsonb gives it back
        rows = [[49.2, -99999 * 10 ** 90], [50.0, 3, 0.5]]

        self.assertEqual(stored_rows(rows), [[49.2, -9.9999e94], [50.0, 3, 0.5]])
        self.assertIsInstance(stored_rows(rows)[0][1], float)
        self.assertIsInstance(stored_rows(rows)[1][1], int)
