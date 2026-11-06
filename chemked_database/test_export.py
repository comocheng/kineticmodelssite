"""The ChemKED YAML export keeps what sync_chemked stored, and PyKED can read it."""

import contextlib
import io
import shutil
import tempfile
import warnings
from pathlib import Path

import yaml
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from pyked import chemked

from .models import ExperimentDataset, IgnitionDelayDatapoint, RCMData

# Shortened from ammonia/Shu_2019 of ChemKED-database (no DOI, as in hydrogen/Naumann_2011),
# with the uncertainty forms found in ChemKED-database added.
CHEMKED_FILE = """\
file-authors:
  - name: Test Author
file-version: 0
chemked-version: 0.5.0
reference:
  authors:
    - name: B. Shu
  journal: Proceedings of the Combustion Institute
  year: 2019
  volume: 37
  pages: 205-211
experiment-type: ignition delay
apparatus:
  kind: shock tube
comments:
  - Reactive volume-time profiles were obtained through personal communication with the authors.
  - Simulations should be carried out using the constant U-V reactor model.
common-properties:
  composition: &comp
    kind: mole fraction
    species:
      - {species-name: NH3, InChI: 1S/H3N/h1H3, amount: [0.1]}
      - {species-name: O2, InChI: 1S/O2/c1-2, amount: [0.15]}
      - {species-name: N2, InChI: 1S/N2/c1-2, amount: [0.75]}
  ignition-type: &ign
    target: OH*
    type: d/dt max
datapoints:
  - temperature:
      - 1213 K
      - {uncertainty-type: absolute, uncertainty: 25 K}
    ignition-delay:
      - 2152 us
      - evaluated-standard-deviation: '0.155261'
        evaluated-standard-deviation-type: relative
        evaluated-standard-deviation-sourcetype: estimated
        evaluated-standard-deviation-method: combined from scatter and reported uncertainty
    pressure:
      - 20 bar
      - evaluated-standard-deviation: 0.5 bar
        evaluated-standard-deviation-type: absolute
    equivalence-ratio: [0.5]
    composition: *comp
    ignition-type: *ign
    time-histories:
      - type: volume
        time: {units: us, column: 0}
        quantity: {units: m3, column: 1}
        values: [[0.0, 1.0], [1.9, 0.9826], [3.9, 0.9729]]
  - temperature: [1100 K]
    ignition-delay:
      - 3000 us
      - {uncertainty-type: absolute, upper-uncertainty: 50 us, lower-uncertainty: 40 us}
    pressure: [20 bar]
    composition: *comp
    ignition-type: *ign
    volume-history:
      time: {units: s, column: 1}
      volume: {units: cm3, column: 0}
      values: [[10.0, 0.0], [9.5, 0.001]]
"""


def load_in_pyked(document, skip_validation=False):
    """Load a ChemKED document with PyKED, as a user of the export does."""
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        return chemked.ChemKED(dict_input=document, skip_validation=skip_validation)


class DatasetExportYamlTests(TestCase):
    def setUp(self):
        self.dataset = self._ingest(CHEMKED_FILE)

    def _ingest(self, text, rel="ammonia/Shu_2019/Shu_2019_st.yaml"):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text(text)
        call_command(
            "sync_chemked", path=str(root), files=[rel], stdout=io.StringIO(), stderr=io.StringIO()
        )
        return ExperimentDataset.objects.get(chemked_file_path=rel)

    def _export(self):
        response = self.client.get(
            reverse("chemked_database:dataset-export", args=[self.dataset.pk]), {"format": "yaml"}
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        return yaml.safe_load(response.content)

    def _point(self, document, kelvin):
        return next(dp for dp in document["datapoints"] if dp["temperature"][0].startswith(kelvin))

    def test_comments_are_kept(self):
        self.assertEqual(self._export()["comments"], yaml.safe_load(CHEMKED_FILE)["comments"])

    def test_time_histories_are_kept(self):
        histories = self._point(self._export(), "1213")["time-histories"]

        self.assertEqual(histories, [{
            "type": "volume",
            "time": {"units": "us", "column": 0},
            "quantity": {"units": "m3", "column": 1},
            "values": [[0.0, 1.0], [1.9, 0.9826], [3.9, 0.9729]],
        }])

    def test_volume_history_is_kept_with_time_first(self):
        history = self._point(self._export(), "1100")["volume-history"]

        self.assertEqual(history, {
            "time": {"units": "s", "column": 0},
            "volume": {"units": "cm3", "column": 1},
            "values": [[0.0, 10.0], [0.001, 9.5]],
        })

    def test_absolute_uncertainties_keep_their_units(self):
        document = self._export()
        hot, cold = self._point(document, "1213"), self._point(document, "1100")

        self.assertEqual(
            hot["temperature"][1], {"uncertainty-type": "absolute", "uncertainty": "25 K"}
        )
        self.assertEqual(hot["pressure"][1]["evaluated-standard-deviation"], "0.5 bar")
        # Only one text is stored per quantity; the other number takes the value's unit
        self.assertEqual(cold["ignition-delay"][1], {
            "uncertainty-type": "absolute",
            "upper-uncertainty": "50 us",
            "lower-uncertainty": "40.0 us",
        })

    def test_relative_evaluated_standard_deviation_is_unchanged(self):
        block = self._point(self._export(), "1213")["ignition-delay"][1]

        self.assertNotIn("uncertainty-type", block)
        # Written as the file gives it, as text
        self.assertEqual(block["evaluated-standard-deviation"], "0.155261")
        self.assertEqual(block["evaluated-standard-deviation-type"], "relative")

    def test_uncertainty_without_type_is_left_out(self):
        quantity = IgnitionDelayDatapoint.objects.get(
            datapoint__dataset=self.dataset, datapoint__temperature=1100.0
        ).ignition_delay_quantity
        quantity.uncertainty_type = ""
        quantity.save()

        with self.assertLogs("chemked_database.views", "WARNING"):
            point = self._point(self._export(), "1100")

        self.assertEqual(point["ignition-delay"], ["3000.0 us"])

    def test_empty_doi_is_left_out(self):
        reference = self._export()["reference"]

        self.assertNotIn("doi", reference)
        self.assertEqual(reference["journal"], "Proceedings of the Combustion Institute")

    def test_ignition_type_given_per_datapoint_is_kept(self):
        # As in the methyl-pentanoate RCM files of ChemKED-database
        document = yaml.safe_load(CHEMKED_FILE)
        del document["common-properties"]["ignition-type"]
        for point in document["datapoints"]:
            point["ignition-type"] = {"target": "pressure", "type": "d/dt max"}
        self.dataset = self._ingest(yaml.safe_dump(document), rel="x/rcm.yaml")

        exported = self._export()

        for point in exported["datapoints"]:
            self.assertEqual(point["ignition-type"], {"target": "pressure", "type": "d/dt max"})
        load_in_pyked(exported)

    def test_equivalence_ratio_is_a_value_unit_list(self):
        self.assertEqual(self._point(self._export(), "1213")["equivalence-ratio"], ["0.5"])

    def test_pyked_reads_the_export(self):
        ck = load_in_pyked(self._export(), skip_validation=True)

        points = {
            round(getattr(dp.temperature.magnitude, "nominal_value", dp.temperature.magnitude)): dp
            for dp in ck.datapoints
        }
        hot, cold = points[1213], points[1100]
        self.assertEqual(hot.temperature.magnitude.std_dev, 25)
        self.assertEqual(hot.volume_history.type, "volume")
        self.assertEqual(list(hot.volume_history.time.to("us").magnitude), [0.0, 1.9, 3.9])
        self.assertEqual(cold.ignition_delay.magnitude.std_dev, 50)
        self.assertEqual(list(cold.volume_history.time.to("s").magnitude), [0.0, 0.001])
        self.assertEqual(list(cold.volume_history.volume.to("cm**3").magnitude), [10.0, 9.5])

    def test_pyked_validates_the_export(self):
        load_in_pyked(self._export())


# Shortened from H2_O2_NOx/Seery_1981/Seery_1981_bsf_p76torr_4 of ChemKED-database (DOI left
# out), keeping its repeated distance of 16.62 mm.
FLAME_FILE = """\
file-authors:
  - name: Test Author
file-version: 0
chemked-version: 0.5.0
reference:
  authors:
    - name: D.J. Seery
    - name: M.F. Zabielski
  journal: Symposium (International) on Combustion
  year: 1981
  volume: 18
  pages: 397-404
experiment-type: speciation measurement
apparatus:
  kind: burner stabilized flame
common-properties:
  temperature: &temperature [300 K]
  pressure: &pressure [76 torr]
  flow-rate: &flow [0.04932 kg * m**-2 * s**-1]
  composition: &comp
    kind: mole fraction
    species:
      - {species-name: H2, InChI: 1S/H2/h1H, amount: [0.408]}
      - {species-name: O2, InChI: 1S/O2/c1-2, amount: [0.148]}
      - {species-name: Ar, InChI: 1S/Ar, amount: [0.44]}
      - {species-name: 'NO', InChI: 1S/NO/c1-2, amount: [0.0041]}
datapoints:
  - independent-variables:
      - {name: distance, units: mm, primary: true}
    concentration-profiles:
      - species-name: 'NO'
        InChI: 1S/NO/c1-2
        quantity: {units: mole fraction}
        values: [[0.0, 0.00384], [11.35, 0.002441], [16.62, 0.002324], [16.62, 0.00216]]
        uncertainty:
          - evaluated-standard-deviation-type: absolute
            evaluated-standard-deviation: 0.000384
            evaluated-standard-deviation-sourcetype: estimated
            evaluated-standard-deviation-method: statistical scatter
    auxiliary-profiles:
      - type: temperature
        independent: {name: distance, units: mm}
        quantity: {units: K}
        values: [[0.0, 300.0], [11.35, 1878.0], [16.62, 1830.0], [16.62, 1830.0]]
    temperature: *temperature
    pressure: *pressure
    flow-rate: *flow
    composition: *comp
"""

# Shortened from pentane/Bugler_2017/Bugler_2017_jsr_p1.05atm of ChemKED-database: species
# with names only. A second datapoint at another residence time, a profile in ppm with a row
# uncertainty column, and reported relative uncertainties (as in ammonia/Dagaut_2022) are added.
JSR_FILE = """\
file-authors:
  - name: Test Author
file-version: 0
chemked-version: 0.5.0
reference:
  authors:
    - name: J. Bugler
  journal: Proceedings of the Combustion Institute
  year: 2017
  volume: 36
  pages: 441-448
experiment-type: speciation measurement
apparatus:
  kind: jet stirred reactor
common-properties:
  reactor-volume: &volume [30 cm3]
  pressure: &pressure [1.05 atm]
  residence-time: &time
    - 2000.0 ms
    - {uncertainty-type: relative, uncertainty: '0.05', uncertainty-sourcetype: reported}
  composition: &comp
    kind: mole fraction
    species:
      - {species-name: NC5H12, amount: [0.01]}
      - species-name: O2
        amount: [0.16, {uncertainty-type: relative, uncertainty: 0.1, uncertainty-sourcetype: reported}]
      - {species-name: HE, amount: [0.83]}
datapoints:
  - independent-variables:
      - {name: temperature, units: K, primary: true}
    concentration-profiles:
      - species-name: NC5H12
        quantity: {units: mole fraction}
        values: [[500.0, 0.01], [525.0, 0.01], [550.0, 0.0098]]
        uncertainty:
          - evaluated-standard-deviation-type: absolute
            evaluated-standard-deviation: 0.0005
            evaluated-standard-deviation-sourcetype: reported
            evaluated-standard-deviation-method: reported uncertainty
      - species-name: CH2O
        InChI: 1S/CH2O/c1-2/h1H2
        quantity: {units: ppm}
        values: [[500.0, 0.0, 0.0], [525.0, 12.0, 1.2], [550.0, 85.0, 8.5]]
        uncertainty:
          - {uncertainty-type: relative, uncertainty: 0.1, uncertainty-sourcetype: reported}
    reactor-volume: *volume
    pressure: *pressure
    residence-time: *time
    composition: *comp
  - independent-variables:
      - {name: temperature, units: K, primary: true}
    concentration-profiles:
      - species-name: NC5H12
        quantity: {units: mole fraction}
        values: [[500.0, 0.01], [600.0, 0.0071]]
    reactor-volume: *volume
    pressure: *pressure
    residence-time: [1000 ms]
    composition: *comp
"""

class HistoryApiTests(TestCase):
    """The REST API serves the time and volume histories that the YAML export writes."""

    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        rel = "ammonia/Shu_2019/Shu_2019_st.yaml"
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text(CHEMKED_FILE)
        call_command(
            "sync_chemked", path=str(root), files=[rel], stdout=io.StringIO(), stderr=io.StringIO()
        )
        self.dataset = ExperimentDataset.objects.get(chemked_file_path=rel)
        response = self.client.get(
            reverse("chemked_database:dataset-export", args=[self.dataset.pk]), {"format": "yaml"}
        )
        self.export = yaml.safe_load(response.content)

    def _exported(self, key):
        return [dp[key] for dp in self.export["datapoints"] if key in dp]

    def _api(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return response.json()

    def test_time_histories_match_the_export(self):
        served = self._api("/api/time-history/", datapoint__dataset=self.dataset.pk)["results"]
        exported = [h for histories in self._exported("time-histories") for h in histories]

        self.assertEqual(len(served), len(exported))
        for row, history in zip(served, exported):
            self.assertEqual(row["history_type"], history["type"])
            self.assertEqual(row["time_units"], history["time"]["units"])
            self.assertEqual(row["quantity_units"], history["quantity"]["units"])
            self.assertEqual(row["values"], history["values"])

    def test_volume_history_matches_the_export(self):
        served = self._api("/api/volume-history/", datapoint__dataset=self.dataset.pk)["results"]
        (exported,) = self._exported("volume-history")

        self.assertEqual(len(served), 1)
        self.assertEqual(served[0]["time_units"], exported["time"]["units"])
        self.assertEqual(served[0]["volume_units"], exported["volume"]["units"])
        self.assertEqual(served[0]["values"], exported["values"])

    def test_datapoints_expand_their_histories(self):
        points = self._api(
            "/api/experiment-datapoint/", dataset=self.dataset.pk,
            expand="time_histories,volume_history", ordering="-temperature",
        )["results"]

        self.assertEqual(
            points[0]["time_histories"][0]["values"], [[0.0, 1.0], [1.9, 0.9826], [3.9, 0.9729]]
        )
        self.assertEqual(points[1]["volume_history"]["values"], [[0.0, 10.0], [0.001, 9.5]])

    def test_history_type_filter(self):
        self.assertEqual(self._api("/api/time-history/", history_type="volume")["count"], 1)
        self.assertEqual(self._api("/api/time-history/", history_type="pressure")["count"], 0)


RCM_FILE = """\
file-authors:
  - name: Test Author
file-version: 0
chemked-version: 0.5.0
reference:
  authors:
    - name: G. Mittal
  journal: Combustion and Flame
  year: 2007
  volume: 149
  pages: 1-11
experiment-type: ignition delay
apparatus:
  kind: rapid compression machine
common-properties:
  composition: &comp
    kind: mole fraction
    species:
      - {species-name: C7H8, InChI: 1S/C7H8/c1-7-5-3-2-4-6-7/h2-6H,1H3, amount: [0.0119]}
      - {species-name: O2, InChI: 1S/O2/c1-2, amount: [0.2096]}
      - {species-name: N2, InChI: 1S/N2/c1-2, amount: [0.7785]}
  ignition-type: &ign
    target: pressure
    type: d/dt max
datapoints:
  - temperature: [297 K]
    pressure: [0.6 bar]
    ignition-delay: [40 ms]
    composition: *comp
    ignition-type: *ign
    rcm-data:
      compressed-temperature: [1022 K]
      compressed-pressure: [45.6 bar]
      compression-time: [27 ms]
  - temperature: [297 K]
    pressure: [0.5 bar]
    ignition-delay: [55 ms]
    composition: *comp
    ignition-type: *ign
"""


class RCMDataApiTests(TestCase):
    """The REST API and the YAML export give the rcm-data of a file: the compressed state."""

    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        rel = "Toluene/Mittal_2007_rcm.yaml"
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text(RCM_FILE)
        call_command(
            "sync_chemked", path=str(root), files=[rel], stdout=io.StringIO(), stderr=io.StringIO()
        )
        self.dataset = ExperimentDataset.objects.get(chemked_file_path=rel)

    def _api(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return response.json()

    def test_rcm_data_endpoint_gives_the_compressed_state(self):
        (row,) = self._api("/api/rcm-data/", datapoint__dataset=self.dataset.pk)["results"]

        self.assertEqual(row["compressed_temperature"], 1022.0)
        self.assertAlmostEqual(row["compressed_pressure"], 45.6e5)
        self.assertAlmostEqual(row["compression_time"], 0.027)
        self.assertEqual(row["compressed_temperature_quantity"]["value"], 1022.0)
        self.assertEqual(row["compressed_temperature_quantity"]["units"], "K")
        self.assertEqual(row["compressed_pressure_quantity"]["units"], "bar")
        self.assertIsNone(row["stroke_quantity"])

    def test_rcm_data_expands_to_its_datapoint(self):
        (row,) = self._api(
            "/api/rcm-data/", datapoint__dataset=self.dataset.pk, expand="datapoint.dataset"
        )["results"]

        self.assertEqual(row["datapoint"]["dataset"]["chemked_file_path"], self.dataset.chemked_file_path)
        self.assertAlmostEqual(row["datapoint"]["pressure"], 0.6e5)

    def test_rcm_data_filters(self):
        self.assertEqual(self._api("/api/rcm-data/", compressed_temperature__gte=1000)["count"], 1)
        self.assertEqual(self._api("/api/rcm-data/", compressed_temperature__gte=1100)["count"], 0)
        points = self._api("/api/experiment-datapoint/", dataset=self.dataset.pk, has_rcm_data="true")
        self.assertEqual(points["count"], 1)
        self.assertEqual(
            self._api("/api/experiment-dataset/", has_rcm_data="true", id__in=self.dataset.pk)["count"], 1
        )

    def test_a_dataset_with_two_rcm_datapoints_is_listed_once(self):
        second = self.dataset.datapoints.filter(rcm_data__isnull=True).get()
        RCMData.objects.create(datapoint=second, compressed_temperature=980.0)

        listed = self._api("/api/experiment-dataset/", has_rcm_data="true", id__in=self.dataset.pk)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(self._api("/api/rcm-data/", datapoint__dataset=self.dataset.pk)["count"], 2)

    def test_datapoints_expand_their_rcm_data(self):
        points = self._api(
            "/api/experiment-datapoint/", dataset=self.dataset.pk, expand="rcm_data", ordering="-pressure",
        )["results"]

        self.assertEqual(points[0]["rcm_data"]["compressed_temperature"], 1022.0)
        self.assertIsNone(points[1].get("rcm_data"))

    def test_export_writes_the_rcm_data_of_the_file(self):
        response = self.client.get(
            reverse("chemked_database:dataset-export", args=[self.dataset.pk]), {"format": "yaml"}
        )
        export = yaml.safe_load(response.content)
        written = [dp.get("rcm-data") for dp in export["datapoints"]]

        self.assertIn(
            {"compressed-temperature": ["1022.0 K"], "compressed-pressure": ["45.6 bar"],
             "compression-time": ["27.0 ms"]},
            written,
        )
        self.assertEqual(sum(1 for entry in written if entry), 1)
        loaded = load_in_pyked(export)
        temperatures = sorted(
            dp.rcm_data.compressed_temperature.magnitude for dp in loaded.datapoints if dp.rcm_data
        )
        self.assertEqual(temperatures, [1022.0])


SPECIATION_KEYS = ("independent-variables", "concentration-profiles", "auxiliary-profiles")


class SpeciationExportTests(TestCase):
    """A speciation measurement is written back as ChemKED 0.5 speciation datapoints."""

    def _round_trip(self, text, rel):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text(text)
        call_command(
            "sync_chemked", path=str(root), files=[rel], stdout=io.StringIO(), stderr=io.StringIO()
        )
        dataset = ExperimentDataset.objects.get(chemked_file_path=rel)
        response = self.client.get(
            reverse("chemked_database:dataset-export", args=[dataset.pk]), {"format": "yaml"}
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.content = response.content.decode()
        return yaml.safe_load(text), yaml.safe_load(response.content)

    def test_profiles_are_written_as_stored(self):
        for text, rel in ((FLAME_FILE, "x/flame.yaml"), (JSR_FILE, "x/jsr.yaml")):
            source, exported = self._round_trip(text, rel)
            with self.subTest(rel=rel):
                self.assertEqual(exported["experiment-type"], "speciation measurement")
                self.assertEqual(exported["apparatus"], source["apparatus"])
                self.assertEqual(len(exported["datapoints"]), len(source["datapoints"]))
                for point, expected in zip(exported["datapoints"], source["datapoints"]):
                    for key in SPECIATION_KEYS:
                        self.assertEqual(point.get(key), expected.get(key), key)

    def test_pyked_validates_the_export(self):
        for text, rel in ((FLAME_FILE, "x/flame.yaml"), (JSR_FILE, "x/jsr.yaml")):
            with self.subTest(rel=rel):
                load_in_pyked(self._round_trip(text, rel)[1])

    def test_flame_conditions(self):
        point = self._round_trip(FLAME_FILE, "x/flame.yaml")[1]["datapoints"][0]

        self.assertEqual(point["temperature"], ["300.0 K"])
        self.assertEqual(point["pressure"], ["76.0 torr"])
        self.assertEqual(point["flow-rate"], ["0.04932 kg * m**-2 * s**-1"])
        # Composition species are written largest amount first
        self.assertEqual(
            [species["species-name"] for species in point["composition"]["species"]],
            ["Ar", "H2", "O2", "NO"],
        )

    def test_reactor_conditions_in_file_order(self):
        first, second = self._round_trip(JSR_FILE, "x/jsr.yaml")[1]["datapoints"]

        # A temperature sweep has no datapoint temperature, so none is written
        self.assertNotIn("temperature", first)
        self.assertEqual(first["residence-time"], [
            "2000.0 ms",
            {"uncertainty-type": "relative", "uncertainty": "0.05", "uncertainty-sourcetype": "reported"},
        ])
        # The second datapoint's own residence time, not the common one
        self.assertEqual(second["residence-time"], ["1000.0 ms"])
        self.assertEqual(first["reactor-volume"], ["30.0 cm3"])
        self.assertIn(
            {"species-name": "NC5H12", "amount": [0.01]}, first["composition"]["species"]
        )

    def test_composition_amount_uncertainty_is_kept(self):
        species = self._round_trip(JSR_FILE, "x/jsr.yaml")[1]["datapoints"][0]["composition"]["species"]

        self.assertIn({
            "species-name": "O2",
            "amount": [
                0.16,
                {"uncertainty-type": "relative", "uncertainty": 0.1, "uncertainty-sourcetype": "reported"},
            ],
        }, species)

    def test_flame_burning_velocity_is_kept(self):
        # As in hydrogen/Vandooren_1991, whose flame files give it
        document = yaml.safe_load(FLAME_FILE)
        document["common-properties"]["laminar-burning-velocity"] = ["131 cm/s"]
        document["datapoints"][0]["laminar-burning-velocity"] = ["131 cm/s"]

        exported = self._round_trip(yaml.safe_dump(document), "x/flame.yaml")[1]

        self.assertEqual(exported["common-properties"]["laminar-burning-velocity"], ["131.0 cm/s"])
        self.assertEqual(exported["datapoints"][0]["laminar-burning-velocity"], ["131.0 cm/s"])
        load_in_pyked(exported)

    def test_common_properties_are_written_apart(self):
        source, exported = self._round_trip(JSR_FILE, "x/jsr.yaml")

        common = exported["common-properties"]
        self.assertEqual(sorted(common), sorted(source["common-properties"]))
        self.assertEqual(common["reactor-volume"], ["30.0 cm3"])
        # Values the datapoints share with them are YAML aliases of their anchors, as in
        # PyKED files
        first, second = exported["datapoints"]
        self.assertIs(first["reactor-volume"], common["reactor-volume"])
        self.assertIs(first["residence-time"], common["residence-time"])
        self.assertIsNot(second["residence-time"], common["residence-time"])
        self.assertIn("reactor-volume: &", self.content)
