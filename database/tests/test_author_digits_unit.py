"""The rates keep the digits the authors wrote. RMG-models wrote its libraries with 6 significant digits
('{0:g}'), so PCI2017/051-Pelucchi's Ea 45025.57 cal/mol was stored as 45025.6. The importer, and the
restore_author_digits command for a database imported before, take each such number from the model's CHEMKIN
line; a number that differs otherwise keeps the library's. A record shared with a model whose authors wrote the
6 digits stays that model's."""
import contextlib
import io
import json
import os
import shutil
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from database import models as db
from database.scripts import author_digits
from database.scripts.import_rmg_models import import_kinetics, import_thermo
from database.services import exports
from database.tests.test_explicit_reverse_unit import model_folder
from database.tests.test_import_rmg_species_unit import MODELS

BI, TER = "cm^3/(mol*s)", "cm^6/(mol^2*s)"


def arrhenius(a, a_units, n, e, e_units="cal/mol"):
    return f"Arrhenius(A=({a},'{a_units}'), n={n}, Ea=({e},'{e_units}'), T0=(1,'K'))"


# label -> (kinetics as RMG-models wrote it: 6 significant digits, reversible)
LIBRARY = {
    "H + O2 <=> O + OH": (arrhenius(3.52123e16, BI, -0.7, 17070.1), True),
    "O + H2 <=> H + OH": (f"MultiArrhenius(arrhenius=[{arrhenius(3.82e12, BI, 0, 7948.06)}, "
                          f"{arrhenius(8.79e14, BI, 0, 19170)}])", True),
    "H + O2 <=> HO2": (f"ThirdBody(arrheniusLow={arrhenius(2.8e18, TER, -0.860012, 0)}, "
                       "efficiencies={'O': 12.5, '[H][H]': 2.0})", True),
    "H2O2 <=> OH + OH": (f"Troe(arrheniusHigh={arrhenius(2e12, 's^-1', 0.9, 48749.1)}, "
                         f"arrheniusLow={arrhenius(2.49e24, BI, -2.3, 48749)}, alpha=0.43, T3=(15.1125,'K'), "
                         "T1=(1e+30,'K'), efficiencies={})", True),
    "HO2 + H <=> H2 + O2": (f"PDepArrhenius(pressures=([0.0394737, 1],'atm'), arrhenius=["
                            f"{arrhenius(1.66e13, BI, 0, 820.123)}, {arrhenius(1.66e13, BI, 0, 820.123)}])", True),
    # 3430.05 is not 3430 rounded: the library's number stays.
    "H2 + OH <=> H2O + H": (arrhenius(2.16e8, BI, 1.51, 3430), True),
    # n differs from the line by more than the 1e-6 the reverse rates are paired with.
    "H2O2 + H <=> HO2 + H2": (arrhenius(6.05e6, BI, 2.31517, 5200.64), True),
    "HO2 + OH <=> H2O + O2": ("Chebyshev(coeffs=[[12.717, -0.21556], [-1.0198, 0.0473], [0.10896, -0.000557]], "
                              "kunits='cm^3/(mol*s)', Tmin=(300,'K'), Tmax=(2500,'K'), Pmin=(0.00986923,'atm'), "
                              "Pmax=(98.6923,'atm'))", True),
}
CHEMKIN = """ELEMENTS H O END
SPECIES H O H2 O2 OH HO2 H2O2 H2O END
REACTIONS
H+O2<=>O+OH                3.521234E+16  -0.700  17070.14
O+H2<=>H+OH                3.820E+12   0.000   7948.057
DUPLICATE
O+H2<=>H+OH                8.790E+14   0.000  19170.0
DUPLICATE
H+O2+M<=>HO2+M             2.800E+18  -0.8600123  0.0
H2O/12.5/ H2/2.0/
H2O2(+M)<=>2OH(+M)         2.000E+12   0.900  48749.12
    LOW / 2.49E+24 -2.3 48749.0 /
    TROE / 0.43 1.511253E+01 1E+30 /
HO2+H<=>H2+O2              1.0  0.0  0.0
    PLOG / 0.03947368 1.660E+13 0.0 820.1234 /
    PLOG / 1.0 1.660E+13 0.0 820.1234 /
H2+OH<=>H2O+H              2.160E+08   1.510   3430.05
H2O2+H<=>HO2+H2            6.050E+06   2.315165407  5200.64
    REV / 1.0E+12 0.0 1000.0 /
HO2+OH<=>H2O+O2            1.0 0.0 0.0
    TCHEB / 300 2500 /
    PCHEB / 0.009869232667160128 98.69232667160128 /
    CHEB / 3 2 /
    CHEB / 12.717 -0.21556 -1.0198 0.0473 0.10896 -0.000557 /
END
"""
# A, Ea; the multi-rate's first Ea; n of the third-body rate; the falloff Ea and T3; a PLOG P and its two Ea;
# n of H2O2 + H; PCHEB Pmin and Pmax.
RESTORED = 12
FIRST = {"H + O2 <=> O + OH": LIBRARY["H + O2 <=> O + OH"]}
SHORT = "REACTIONS\nH+O2<=>O+OH 3.52123E+16 -0.700 17070.1\nEND\n"       # its authors wrote 6 digits
SAME = "REACTIONS\nH+O2<=>O+OH 3.521234E+16 -0.700 17070.14\nEND\n"      # the authors of "long" too
KELVIN = ({"H + O2 <=> O + OH": (arrhenius(2.4e13, BI, 0.47, 292013, "J/mol"), True)},
          "REACTIONS MOLES KELVINS\nH+O2<=>O+OH 2.400E+13 0.4700 35121.00\nEND\n")
H_O2 = ((-1, "H"), (-1, "O2"), (1, "O"), (1, "OH"))


def import_models(directory, restore=True):
    """long, short, same and kelvin, imported in this order; without *restore*, as before author_digits."""
    found = {}
    with contextlib.nullcontext() if restore else mock.patch.object(author_digits, "can_restore", return_value=False):
        for name, entries, chemkin in (("long", LIBRARY, CHEMKIN), ("short", FIRST, SHORT), ("same", FIRST, SAME),
                                       ("kelvin", *KELVIN)):
            model = db.KineticModel.objects.create(model_name=name)
            thermo_path, kinetics_path = model_folder(directory, name, entries, chemkin)
            import_thermo(thermo_path, model, MODELS)
            found[name] = (model, import_kinetics(kinetics_path, model, MODELS))
    return found


def link(model, *species):
    """The model's kinetics link of the reaction with these species (coefficient, name)."""
    names = dict(db.SpeciesName.objects.filter(kinetic_model=model).values_list("species_id", "name"))
    for found in db.KineticsComment.objects.filter(kinetic_model=model).select_related("kinetics__reaction"):
        stoichiometry = sorted((s.coeff, names[s.species_id]) for s in found.kinetics.reaction.stoichiometry_set.all())
        if stoichiometry == sorted(species):
            return found
    raise AssertionError(f"{model} has no link for {species}")


class Checks:
    """The rates of the four models with the authors' digits."""

    def raw(self, name, *species):
        return link(self.models[name], *species).kinetics.raw_data

    def test_elementary_rate(self):
        raw = self.raw("long", *H_O2)
        self.assertEqual((raw["a"], raw["n"], raw["e"]), (3.521234e16, -0.7, 17070.14))
        self.assertAlmostEqual(raw["e_si"] / (17070.14 * 4.184), 1.0, places=14)
        self.assertAlmostEqual(raw["a_si"] / 3.521234e10, 1.0, places=14)

    def test_duplicate_lines(self):
        first, second = self.raw("long", (-1, "O"), (-1, "H2"), (1, "H"), (1, "OH"))["arrhenius_set"]
        self.assertEqual((first["e"], second["e"]), (7948.057, 19170.0))

    def test_third_body_falloff_and_plog(self):
        self.assertEqual(self.raw("long", (-1, "H"), (-1, "O2"), (1, "HO2"))["low_arrhenius"]["n"], -0.8600123)
        troe = self.raw("long", (-1, "H2O2"), (2, "OH"))
        self.assertEqual((troe["high_arrhenius"]["e"], troe["low_arrhenius"]["e"], troe["t3"], troe["alpha"]),
                         (48749.12, 48749.0, 15.11253, 0.43))
        low, high = self.raw("long", (-1, "HO2"), (-1, "H"), (1, "H2"), (1, "O2"))["pressure_set"]
        self.assertEqual((low["pressure"], high["pressure"]), (0.03947368 * 101325, 101325.0))
        self.assertEqual((low["arrhenius"]["e"], high["arrhenius"]["e"]), (820.1234, 820.1234))

    def test_other_difference_keeps_the_library_number(self):
        self.assertEqual(self.raw("long", (-1, "H2"), (-1, "OH"), (1, "H2O"), (1, "H"))["e"], 3430.0)

    def test_chebyshev_pressure_range(self):
        kinetics = link(self.models["long"], (-1, "HO2"), (-1, "OH"), (1, "H2O"), (1, "O2")).kinetics
        self.assertEqual((kinetics.min_pressure, kinetics.max_pressure),
                         (0.009869232667160128 * 101325, 98.69232667160128 * 101325))
        self.assertEqual((kinetics.min_temp, kinetics.max_temp), (300.0, 2500.0))
        self.assertEqual(kinetics.raw_data["coefficient_matrix"][2][1], -0.000557)

    def test_shared_record_follows_the_authors(self):
        long, short, same = (link(self.models[name], *H_O2) for name in ("long", "short", "same"))
        self.assertEqual(long.kinetics_id, same.kinetics_id)
        self.assertNotEqual(long.kinetics_id, short.kinetics_id)
        self.assertEqual(short.kinetics.raw_data["e"], 17070.1)
        self.assertEqual(db.Kinetics.objects.filter(reaction=long.kinetics.reaction, raw_data__type="arrhenius")
                         .count(), 3)      # long and same, short, kelvin

    def test_kelvin_model(self):
        raw = self.raw("kelvin", *H_O2)
        self.assertEqual((raw["e"], raw["e_units"]), (292012.571112, "J/mol"))
        self.assertAlmostEqual(raw["e"] / 8.314472, 35121.00, places=9)

    def test_fingerprints_are_current(self):
        from database.services.chemistry_index import kinetics_fingerprint
        for kinetics in db.Kinetics.objects.all():
            self.assertEqual(kinetics.rate_fingerprint, kinetics_fingerprint(kinetics) or [], kinetics.raw_data)


class ImporterTests(Checks, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.directory = tempfile.mkdtemp()
        imported = import_models(cls.directory)
        cls.models = {name: model for name, (model, _) in imported.items()}
        cls.counts = {name: counts for name, (_, counts) in imported.items()}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory)
        super().tearDownClass()

    def test_counts(self):
        self.assertEqual(self.counts["long"]["author_digits"], RESTORED)
        self.assertEqual(self.counts["same"]["author_digits"], 2)
        self.assertNotIn("author_digits", self.counts["short"])
        self.assertEqual(self.counts["long"]["failed"], 0)

    def test_the_reverse_rate_is_paired_with_the_authors_rate(self):
        found = link(self.models["long"], (-1, "H2O2"), (-1, "H"), (1, "HO2"), (1, "H2"))
        self.assertEqual(found.kinetics.raw_data["n"], 2.315165407)
        self.assertEqual(found.reverse_rate["terms"][0]["arrhenius"]["a"], 1.0e12)

    def test_chemkin_download_writes_the_authors_digits(self):
        files = exports._generate_chemkin_files(self.models["long"])
        (text,) = [v.decode() for k, v in files.items() if k.endswith("_chem.inp")]
        self.assertIn("17.07014", text)
        self.assertIn("48.74912", text)
        self.assertNotRegex(text, r"17\.0701(?!4)")


class RestoreCommandTests(Checks, TestCase):
    """A database imported before author_digits: the command gives what the importer gives now."""

    @classmethod
    def setUpTestData(cls):
        cls.directory = tempfile.mkdtemp()
        imported = import_models(cls.directory, restore=False)
        cls.models = {name: model for name, (model, _) in imported.items()}
        cls.before = {name: link(model, *H_O2).kinetics_id for name, model in cls.models.items()}
        cls.dry_run = cls.command()
        cls.after_dry_run = {name: link(model, *H_O2).kinetics.raw_data for name, model in cls.models.items()}
        cls.report = cls.command("--apply")
        cls.again = cls.command("--apply")

    @classmethod
    def command(cls, *args):
        path = os.path.join(cls.directory, f"report{len(args)}{os.urandom(4).hex()}.json")
        call_command("restore_author_digits", "--path", cls.directory, "--report", path, *args, stdout=io.StringIO())
        with open(path) as handle:
            return json.load(handle)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory)
        super().tearDownClass()

    def test_before(self):
        # The four models' libraries: long, short and same had one record.
        self.assertEqual(len({self.before[n] for n in ("long", "short", "same")}), 1)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(sum(self.dry_run["numbers"].values()), RESTORED + 2 + 1)
        self.assertEqual(self.after_dry_run["long"]["e"], 17070.1)
        self.assertEqual(self.after_dry_run["kelvin"]["e"], 292013)

    def test_report(self):
        self.assertEqual(sum(self.report["numbers"].values()), RESTORED + 2 + 1)
        self.assertEqual(self.report["numbers"]["PCHEB"], 2)
        self.assertEqual(self.report["other"], {"Ea": 1})
        # long and same leave the record that short keeps; the kelvin model's has only it.
        self.assertEqual(self.report["records"]["new"], 1)
        self.assertEqual(self.report["links_moved"], 2)

    def test_record_ids(self):
        self.assertEqual(link(self.models["short"], *H_O2).kinetics_id, self.before["short"])
        self.assertEqual(link(self.models["kelvin"], *H_O2).kinetics_id, self.before["kelvin"])

    def test_second_run_changes_nothing(self):
        self.assertEqual((self.again["numbers"], self.again["links"], self.again["records"]), ({}, 0, {}))

    def test_reverse_rates_after_the_digits(self):
        # The REV line pairs with the forward rate as written; with n 2.31517 it did not.
        found = link(self.models["long"], (-1, "H2O2"), (-1, "H"), (1, "HO2"), (1, "H2"))
        self.assertIsNone(found.reverse_rate)
        call_command("import_explicit_reverse_rates", "--path", self.directory, "--apply", "--model", "long",
                     stdout=io.StringIO())
        found.refresh_from_db()
        self.assertEqual(found.reverse_rate["terms"][0]["arrhenius"]["a"], 1.0e12)


class RulesTests(SimpleTestCase):
    def test_is_rounding(self):
        self.assertTrue(author_digits.is_rounding(45025.57, 45025.6))
        self.assertTrue(author_digits.is_rounding(17041.11, 17041.099999999995))    # RMG's cal/mol round trip
        self.assertFalse(author_digits.is_rounding(45025.6, 45025.6))
        self.assertFalse(author_digits.is_rounding(3430.05, 3430.0))
        self.assertTrue(author_digits.is_rounding(1.315789 * 101325, 1.31579 * 101325, 101325.0))

    def test_decimal(self):
        self.assertEqual(author_digits.decimal(43950.16900000001), 43950.169)
        self.assertEqual(author_digits.decimal(292012.57111200003), 292012.571112)
        self.assertEqual(author_digits.decimal(2750.62938509725), 2750.62938509725)
        self.assertEqual(author_digits.decimal(0.0), 0.0)
        self.assertEqual(author_digits.decimal(1.2308000000000002e+90), 1.2308e90)
