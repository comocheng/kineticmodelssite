"""Numeric value fields hold SI units; the linked ValueWithUnit keeps the file's value and unit."""

import importlib
import io
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from chemked_database.management.commands.sync_chemked import parse_value_unit
from chemked_database.models import (
    CommonProperties,
    ExperimentDatapoint,
    ExperimentDataset,
    IgnitionDelayDatapoint,
    ValueWithUnit,
)
from chemked_database.units import UnitConversionError, quantity_to_si, to_si

migration = importlib.import_module("chemked_database.migrations.0031_store_numeric_values_in_si")

# The fields of models that still exist; 0033 removed the four old speciation models
CURRENT_QUANTITY_FIELDS = [
    entry for entry in migration.QUANTITY_FIELDS
    if entry[0] in {model.__name__ for model in apps.get_app_config("chemked_database").get_models()}
]

ATM = 101325.0
TORR = ATM / 760.0


class ToSITests(SimpleTestCase):
    def test_pressure(self):
        self.assertAlmostEqual(to_si(15.6, "atm", "pressure"), 15.6 * ATM)
        self.assertAlmostEqual(to_si(20, "bar", "pressure"), 2.0e6)
        self.assertAlmostEqual(to_si(30, "Torr", "pressure"), 30 * TORR)
        self.assertAlmostEqual(to_si(30, "torr", "pressure"), 30 * TORR)
        self.assertAlmostEqual(to_si(1, "standard_atmosphere", "pressure"), ATM)

    def test_time(self):
        self.assertAlmostEqual(to_si(13797, "us", "time"), 0.013797)
        self.assertAlmostEqual(to_si(1.2, "ms", "time"), 1.2e-3)
        self.assertAlmostEqual(to_si(31, "microsecond", "time"), 31e-6)

    def test_other_kinds(self):
        self.assertAlmostEqual(to_si(25, "degC", "temperature"), 298.15)
        self.assertAlmostEqual(to_si(40, "cm/s", "velocity"), 0.4)
        self.assertAlmostEqual(to_si(0.05, "1/ms", "rate"), 50.0)
        self.assertAlmostEqual(to_si(2, "mm", "length"), 2e-3)
        self.assertAlmostEqual(to_si(30, "cm3", "volume"), 3e-5)
        self.assertAlmostEqual(to_si(0.1, "kg * m**-2 * s**-1", "mass_flux"), 0.1)
        self.assertAlmostEqual(to_si(0.01, "g/cm2/s", "mass_flux"), 0.1)

    def test_unit_split_from_number_ending_in_a_point(self):
        # "660. K" was stored as 660 with units ". K"
        self.assertEqual(to_si(660, ". K", "temperature"), 660.0)
        self.assertAlmostEqual(to_si(2, ". ms", "time"), 2e-3)

    def test_missing_or_wrong_units_raise(self):
        for units, kind in (("", "pressure"), (None, "time"), ("K", "pressure"), ("C", "temperature"),
                            ("furlong", "time"), ("not a unit", "pressure")):
            with self.subTest(units=units, kind=kind):
                with self.assertRaises(UnitConversionError):
                    to_si(1.0, units, kind)

    def test_quantity_without_number(self):
        self.assertIsNone(to_si(None, "atm", "pressure"))
        self.assertIsNone(quantity_to_si(None, "pressure"))
        self.assertIsNone(quantity_to_si(ValueWithUnit(value=None, units="atm", value_text="high"), "pressure"))
        self.assertAlmostEqual(quantity_to_si(ValueWithUnit(value=2.0, units="atm"), "pressure"), 2 * ATM)


class ParseValueUnitTests(SimpleTestCase):
    def test_number_ending_in_a_point(self):
        self.assertEqual(parse_value_unit("660. K")[:2], (660.0, "K"))

    def test_list_and_exponent_forms(self):
        self.assertEqual(parse_value_unit(["13797 us", {"uncertainty-type": "relative"}])[:2], (13797.0, "us"))
        self.assertEqual(parse_value_unit("1.5e-3 s")[:2], (1.5e-3, "s"))
        self.assertEqual(parse_value_unit(".5 atm")[:2], (0.5, "atm"))


CHEMKED_FILE = """\
file-version: 0
chemked-version: 0.4.1
file-authors:
  - name: Test Author
reference:
  authors:
    - name: Test Author
  year: 2020
  journal: Test Journal
experiment-type: ignition delay
apparatus:
  kind: shock tube
  institution: Test University
  facility: Test shock tube
common-properties:
  pressure: [20 bar]
  composition:
    kind: mole fraction
    species:
      - species-name: H2
        InChI: 1S/H2/h1H
        amount: [0.1]
      - species-name: O2
        InChI: 1S/O2/c1-2
        amount: [0.05]
      - species-name: Ar
        InChI: 1S/Ar
        amount: [0.85]
  ignition-type:
    target: pressure
    type: d/dt max
datapoints:
  - temperature: [1100. K]
    pressure: [15.6 atm]
    ignition-delay: [250 us]
    pressure-rise: [0.05 1/ms]
    ignition-type: {target: pressure, type: d/dt max}
  - temperature: [1000 K]
    pressure: [30 Torr]
    ignition-delay: [1.2 ms]
    ignition-type: {target: pressure, type: d/dt max}
  - temperature: [900 K]
    pressure: [2 furlong]
    ignition-delay: [3 ms]
    ignition-type: {target: pressure, type: d/dt max}
"""


class SyncChemkedSITests(TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.rel = "hydrogen/Test_2020/Test_2020_ST.yaml"
        (self.root / self.rel).parent.mkdir(parents=True)
        (self.root / self.rel).write_text(CHEMKED_FILE)
        self.err = io.StringIO()
        call_command("sync_chemked", path=str(self.root), files=[self.rel],
                     stdout=io.StringIO(), stderr=self.err)
        self.dataset = ExperimentDataset.objects.get(chemked_file_path=self.rel)

    def test_datapoint_values_are_in_si(self):
        points = list(self.dataset.datapoints.order_by("-temperature"))
        self.assertEqual(len(points), 2)
        first, second = points

        self.assertEqual(first.temperature, 1100.0)
        self.assertAlmostEqual(first.pressure, 15.6 * ATM)
        self.assertAlmostEqual(second.pressure, 30 * TORR)

        delay = IgnitionDelayDatapoint.objects.get(datapoint=first)
        self.assertAlmostEqual(delay.ignition_delay, 250e-6)
        self.assertAlmostEqual(delay.pressure_rise, 50.0)
        self.assertAlmostEqual(IgnitionDelayDatapoint.objects.get(datapoint=second).ignition_delay, 1.2e-3)

    def test_quantities_keep_the_file_values(self):
        first = self.dataset.datapoints.get(temperature=1100.0)
        self.assertEqual((first.pressure_quantity.value, first.pressure_quantity.units), (15.6, "atm"))
        self.assertEqual((first.temperature_quantity.value, first.temperature_quantity.units), (1100.0, "K"))
        delay = IgnitionDelayDatapoint.objects.get(datapoint=first)
        self.assertEqual((delay.ignition_delay_quantity.value, delay.ignition_delay_quantity.units), (250.0, "us"))

    def test_common_properties_in_si(self):
        common = CommonProperties.objects.get(dataset=self.dataset)
        self.assertAlmostEqual(common.pressure, 2.0e6)
        self.assertEqual(common.pressure_quantity.units, "bar")

    def test_unconvertible_unit_skips_the_datapoint(self):
        self.assertFalse(self.dataset.datapoints.filter(temperature=900.0).exists())
        self.assertIn("furlong", self.err.getvalue())

    def test_range_filter_finds_the_si_values(self):
        delays = IgnitionDelayDatapoint.objects.filter(datapoint__dataset=self.dataset)
        self.assertEqual(delays.filter(ignition_delay__lte=1e-3).count(), 1)
        self.assertEqual(delays.filter(ignition_delay__gte=1.0).count(), 0)


class ConvertExistingRowsTests(TestCase):
    """The 0031 data migration, run on rows as the old sync_chemked stored them."""

    def setUp(self):
        self.dataset = ExperimentDataset.objects.create(
            chemked_file_path="test/old_import.yaml", experiment_type="ignition delay"
        )

    def _datapoint(self, temperature, t_units, pressure, p_units, **extra):
        return ExperimentDatapoint.objects.create(
            dataset=self.dataset,
            temperature=temperature,
            pressure=pressure,
            temperature_quantity=ValueWithUnit.objects.create(value=temperature, units=t_units),
            pressure_quantity=ValueWithUnit.objects.create(value=pressure, units=p_units),
            **extra,
        )

    @mock.patch.object(migration, "QUANTITY_FIELDS", CURRENT_QUANTITY_FIELDS)
    def test_converts_raw_numbers_and_keeps_converted_ones(self):
        raw = self._datapoint(660.0, ". K", 15.6, "atm", residence_time=3000.0, residence_time_units="ms")
        delay = IgnitionDelayDatapoint.objects.create(
            datapoint=raw,
            ignition_delay=13797.0,
            ignition_delay_quantity=ValueWithUnit.objects.create(value=13797.0, units="us"),
        )
        converted = ExperimentDatapoint.objects.create(
            dataset=self.dataset,
            temperature=1000.0,
            pressure=ATM,
            pressure_quantity=ValueWithUnit.objects.create(value=1.0, units="standard_atmosphere"),
        )
        no_quantity = ExperimentDatapoint.objects.create(dataset=self.dataset, temperature=900.0, pressure=5e5)
        bad_unit = self._datapoint(800.0, "K", 2.0, "furlong")
        common = CommonProperties.objects.create(
            dataset=self.dataset,
            reactor_volume=30.0,
            reactor_volume_units="cm3",
            reactor_volume_quantity=ValueWithUnit.objects.create(value=30.0, units="cm3"),
        )

        migration.convert_to_si(apps, None)

        for obj in (raw, delay, converted, no_quantity, bad_unit, common):
            obj.refresh_from_db()
        self.assertEqual(raw.temperature, 660.0)
        self.assertAlmostEqual(raw.pressure, 15.6 * ATM)
        self.assertEqual((raw.residence_time, raw.residence_time_units), (3.0, "s"))
        self.assertAlmostEqual(delay.ignition_delay, 0.013797)
        self.assertEqual(delay.ignition_delay_quantity.value, 13797.0)
        self.assertAlmostEqual(converted.pressure, ATM)
        self.assertEqual(no_quantity.pressure, 5e5)
        self.assertEqual(bad_unit.pressure, 2.0)
        self.assertAlmostEqual(common.reactor_volume, 3e-5)
        self.assertEqual(common.reactor_volume_units, "m3")

        # A second run changes nothing.
        before = list(ExperimentDatapoint.objects.order_by("pk").values_list(
            "temperature", "pressure", "residence_time", "residence_time_units"))
        migration.convert_to_si(apps, None)
        after = list(ExperimentDatapoint.objects.order_by("pk").values_list(
            "temperature", "pressure", "residence_time", "residence_time_units"))
        self.assertEqual(before, after)
        delay.refresh_from_db()
        self.assertAlmostEqual(delay.ignition_delay, 0.013797)
