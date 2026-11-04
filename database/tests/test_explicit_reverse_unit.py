"""The model's own reverse rates: REV / A n Ea / on a reversible CHEMKIN line.

RMG-models keeps only the forward rate of such a line (Malewicki 17 NC12H26 + H <=> C12H25-1 + H2,
rev / 8.926E+03 2.70 1.055E+04 /), so the exports gave the reverse rate from thermochemistry. The
importer now reads the REV from the model's CHEMKIN file onto the model's link, the CHEMKIN export
writes it after the entry, and ck2yaml makes it a second, irreversible reaction in the Cantera export.
"""
import csv
import math
import os
import re
import shutil
import tempfile

import cantera as ct
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from database import models as db
from database.scripts import explicit_reverse
from database.scripts.import_rmg_models import import_kinetics, import_thermo
from database.services import exports
from database.tests.test_import_rmg_species_unit import MODELS, NASA_TEXT
from database.tests.test_repeated_species_export_unit import sides

ADJ = {
    "H": "multiplicity 2\n1 H u1 p0 c0",
    "O": "multiplicity 3\n1 O u2 p2 c0",
    "H2": "1 H u0 p0 c0 {2,S}\n2 H u0 p0 c0 {1,S}",
    "O2": "multiplicity 3\n1 O u1 p2 c0 {2,S}\n2 O u1 p2 c0 {1,S}",
    "OH": "multiplicity 2\n1 O u1 p2 c0 {2,S}\n2 H u0 p0 c0 {1,S}",
    "HO2": "multiplicity 2\n1 O u0 p2 c0 {2,S} {3,S}\n2 O u1 p2 c0 {1,S}\n3 H u0 p0 c0 {1,S}",
    "H2O2": "1 O u0 p2 c0 {2,S} {3,S}\n2 O u0 p2 c0 {1,S} {4,S}\n3 H u0 p0 c0 {1,S}\n4 H u0 p0 c0 {2,S}",
    "H2O": "1 O u0 p2 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}",
}
ARR = "Arrhenius(A=({a},'{units}'), n={n}, Ea=({e},'cal/mol'), T0=(1,'K'))"
BI = "cm^3/(mol*s)"
# label -> (kinetics, reversible), as RMG-models writes them: the forward rate only.
ENTRIES = {
    "H + O2 <=> O + OH": (ARR.format(a=3.52e16, units=BI, n=-0.7, e=17070), True),
    "O + H2 <=> H + OH": ("MultiArrhenius(arrhenius=[" + ARR.format(a=3.82e12, units=BI, n=0, e=7948) + ", "
                          + ARR.format(a=8.79e14, units=BI, n=0, e=19170) + "])", True),
    "H + O2 <=> HO2": ("ThirdBody(arrheniusLow=" + ARR.format(a=2.8e18, units="cm^6/(mol^2*s)", n=-0.86, e=0)
                       + ", efficiencies={})", True),
    "H2O2 <=> OH + OH": ("Troe(arrheniusHigh=" + ARR.format(a=2e12, units="s^-1", n=0.9, e=48749)
                         + ", arrheniusLow=" + ARR.format(a=2.49e24, units=BI, n=-2.3, e=48749)
                         + ", alpha=0.43, T3=(1e-30,'K'), T1=(1e+30,'K'), efficiencies={})", True),
    "HO2 + H <=> H2 + O2": (ARR.format(a=1.66e13, units=BI, n=0, e=820), True),
    # REV / 0 0 0 /: irreversible, as RMG-models makes it.
    "H2 + OH => H2O + H": (ARR.format(a=2.16e8, units=BI, n=1.51, e=3430), False),
    # A REV line that RMG-models made irreversible (PCI2013/335-Wang line 13319): not written.
    "HO2 + OH => H2O + O2": (ARR.format(a=2.89e13, units=BI, n=0, e=-497), False),
}
CHEMKIN = """ELEMENTS H O END
SPECIES H O H2 O2 OH HO2 H2O2 H2O XX END
REACTIONS
H+O2<=>O+OH                3.520E+16  -0.700  17070.0
    rev /  7.04E+13 -0.26 150.0 /
O+H2<=>H+OH                3.820E+12   0.000   7948.0
DUPLICATE
REV/2.0D+12 0.0 5000.0/
O+H2<=>H+OH                8.790E+14   0.000  19170.0
DUPLICATE
H+O2+M<=>HO2+M             2.800E+18  -0.860      0.0
REV / 3.0E+19 -1.0 49000.0/
H2O2(+M)<=>2OH(+M)         2.000E+12   0.900  48749.0
    LOW / 2.49E+24 -2.3 48749.0 /
    TROE / 0.43 1E-30 1E+30 /
    REV/ 1.233E+66 -14.2349 63046.4/
HO2+H<=>H2+O2              1.660E+13   0.000    820.0
H2+OH<=>H2O+H              2.160E+08   1.510   3430.0
    REV / 0.0 0.0 0.0 /
HO2+OH<=>H2O+O2            2.890E+13   0.000   -497.0
    REV / 3.0E+15 0.0 70000.0 /
XX+H<=>OH+H2               1.000E+13   0.000      0.0
    REV / 1.0E+12 0.0 0.0 /
END
"""
# The same forward rate of H + O2 <=> O + OH, without REV: the reverse comes from thermochemistry.
PLAIN = """ELEMENTS H O END
SPECIES H O H2 O2 OH END
REACTIONS
H+O2<=>O+OH                3.520E+16  -0.700  17070.0
END
"""


def model_folder(root, name, entries, chemkin):
    """An RMG-models folder: thermo and kinetics libraries, import.sh and the CHEMKIN file."""
    folder = os.path.join(root, name)
    thermo_dir, kinetics_dir = (os.path.join(folder, d) for d in ("RMG-Py-thermo-library", "RMG-Py-kinetics-library"))
    os.makedirs(thermo_dir)
    os.makedirs(kinetics_dir)
    thermo_path, kinetics_path = os.path.join(thermo_dir, "ThermoLibrary.py"), os.path.join(kinetics_dir, "reactions.py")
    with open(thermo_path, "w") as handle:
        handle.write('name = "test"\nshortDesc = ""\nlongDesc = """"""\n')
        for index, (label, adjacency) in enumerate(ADJ.items()):
            handle.write(f'entry(index={index}, label="{label}", molecule="""\n{adjacency}\n""", '
                         f'thermo={NASA_TEXT}, shortDesc="""test""", longDesc="""""")\n')
    with open(os.path.join(kinetics_dir, "dictionary.txt"), "w") as handle:
        for label, adjacency in ADJ.items():
            handle.write(f"{label}\n{adjacency}\n\n")
    with open(kinetics_path, "w") as handle:
        handle.write('name = "test"\nshortDesc = ""\nlongDesc = """"""\nautoGenerated=False\n')
        for index, (label, (kinetics, reversible)) in enumerate(entries.items()):
            flag = "" if reversible else "reversible = False, "
            duplicate = "duplicate = True, " if kinetics.startswith("Multi") else ""
            handle.write(f'entry(index={index}, label="{label}", degeneracy=1.0, {flag}{duplicate}'
                         f'kinetics={kinetics}, shortDesc="""The chemkin file reaction is {label}""")\n')
    with open(os.path.join(folder, "import.sh"), "w") as handle:
        handle.write("python import.py \\\n\t--species chem.inp \\\n\t--reactions chem.inp \\\n")
    with open(os.path.join(folder, "chem.inp"), "w") as handle:
        handle.write(chemkin)
    return thermo_path, kinetics_path


class RevLinesTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def lines(self, text, names, ea_to_j=4.184, molecules=False):
        path = os.path.join(self.directory, "chem.inp")
        with open(path, "w") as handle:
            handle.write(text)
        return {line["line"]: line for line in explicit_reverse.rev_lines(path, names, ea_to_j, molecules)}

    def test_forms_of_rev(self):
        lines = self.lines(CHEMKIN, set(ADJ) | {"XX"})
        # Lower case and spaces; D exponents; Ea glued to the slash; not REV / 0 0 0 /.
        self.assertEqual(sorted(lines), [4, 6, 11, 13, 20, 22])
        self.assertEqual(lines[4]["rev"], (7.04e13, -0.26, 150.0))
        self.assertEqual(lines[4]["rev_text"], "rev /  7.04E+13 -0.26 150.0 /")
        self.assertEqual(lines[6]["rev"], (2e12, 0.0, 5000.0))
        self.assertTrue(lines[6]["duplicate"])
        self.assertEqual(lines[11]["rev"], (3e19, -1.0, 49000.0))
        self.assertEqual((lines[11]["collider"], lines[11]["falloff"]), ("M", False))
        self.assertEqual((lines[13]["collider"], lines[13]["falloff"]), ("M", True))
        self.assertEqual(lines[13]["rev"], (1.233e66, -14.2349, 63046.4))    # Malewicki 17 line 23076
        self.assertFalse(lines[4]["duplicate"] or lines[4]["falloff"] or lines[4]["collider"])

    def test_rev_on_an_irreversible_line_is_not_read(self):
        lines = self.lines("REACTIONS\nH+O2=>O+OH 1e16 0 0\nREV / 1e13 0 0 /\nEND\n", set(ADJ))
        self.assertEqual(lines, {})

    def test_units(self):
        text = "REACTIONS KELVINS MOLECULES\nH+O2(+AR)<=>HO2(+AR) 1e-12 0 100\nLOW/1e-30 0 0/\nREV / 2e-11 0.5 3000 /\nEND\n"
        (line,) = self.lines(text, set(ADJ) | {"AR"}, ea_to_j=8.314462618, molecules=True).values()
        self.assertEqual(line["collider"], "AR")
        rate = explicit_reverse.reverse_arrhenius(line, 8.314462618, molecules=True)
        # HO2 => H + O2 (+AR) is first order (fall-off): A per molecule is A per mole; K -> J/mol.
        self.assertEqual(rate["a_units"], "s^-1")
        self.assertAlmostEqual(rate["a"], 2e-11)
        self.assertEqual(rate["e_units"], "J/mol")
        self.assertAlmostEqual(rate["e"], 3000 * 8.314462618)
        # A three-body line counts M: H + O2 + M => ... of two products and M is third order.
        line = dict(line, falloff=False, products=["O", "OH"])
        rate = explicit_reverse.reverse_arrhenius(line, 4.184, molecules=True)
        self.assertEqual(rate["a_units"], "cm^6/(mol^2*s)")
        self.assertAlmostEqual(rate["a"] / (2e-11 * 6.02214076e23 ** 2), 1.0)


class ExplicitReverseRatesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.directory = tempfile.mkdtemp()
        cls.model = db.KineticModel.objects.create(model_name="rev")
        cls.plain = db.KineticModel.objects.create(model_name="plain")
        for model, entries, chemkin in ((cls.model, ENTRIES, CHEMKIN),
                                        (cls.plain, {"H + O2 <=> O + OH": ENTRIES["H + O2 <=> O + OH"]}, PLAIN)):
            thermo_path, kinetics_path = model_folder(cls.directory, model.model_name, entries, chemkin)
            import_thermo(thermo_path, model, MODELS)
            cls_counts = import_kinetics(kinetics_path, model, MODELS)
            if model is cls.model:
                cls.counts = cls_counts

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory)
        super().tearDownClass()

    def link(self, model, *species):
        """The model's kinetics link of the reaction with these species (coefficient, name)."""
        names = dict(db.SpeciesName.objects.filter(kinetic_model=model).values_list("species_id", "name"))
        for link in db.KineticsComment.objects.filter(kinetic_model=model).select_related("kinetics__reaction"):
            stoichiometry = sorted((s.coeff, names[s.species_id]) for s in link.kinetics.reaction.stoichiometry_set.all())
            if stoichiometry == sorted(species):
                return link
        raise AssertionError(f"{model} has no link for {species}")

    def test_import_keeps_the_rev(self):
        link = self.link(self.model, (-1, "H"), (-1, "O2"), (1, "O"), (1, "OH"))
        (term,) = link.reverse_rate["terms"]
        self.assertEqual((term["line"], term["text"]), (4, "rev /  7.04E+13 -0.26 150.0 /"))
        rate = term["arrhenius"]
        self.assertEqual((rate["a"], rate["a_units"], rate["n"], rate["e"], rate["e_units"]),
                         (7.04e13, "cm^3/(mol*s)", -0.26, 150.0, "cal/mol"))
        self.assertAlmostEqual(rate["e_si"], 150.0 * 4.184)
        self.assertEqual(self.counts["reverse_rates"], 4)

    def test_each_duplicate_line_has_its_own_rev(self):
        link = self.link(self.model, (-1, "O"), (-1, "H2"), (1, "H"), (1, "OH"))
        first, second = link.reverse_rate["terms"]
        self.assertEqual((first["line"], first["arrhenius"]["a"], first["arrhenius"]["e"]), (6, 2e12, 5000.0))
        self.assertIsNone(second)

    def test_third_body_and_falloff_orders(self):
        third = self.link(self.model, (-1, "H"), (-1, "O2"), (1, "HO2"))
        self.assertEqual(third.reverse_rate["terms"][0]["arrhenius"]["a_units"], "cm^3/(mol*s)")
        falloff = self.link(self.model, (-1, "H2O2"), (2, "OH"))
        self.assertEqual(falloff.reverse_rate["terms"][0]["arrhenius"]["a_units"], "cm^3/(mol*s)")

    def test_no_rev_where_the_model_gives_none(self):
        self.assertIsNone(self.link(self.model, (-1, "HO2"), (-1, "H"), (1, "H2"), (1, "O2")).reverse_rate)
        self.assertIsNone(self.link(self.model, (-1, "H2"), (-1, "OH"), (1, "H2O"), (1, "H")).reverse_rate)
        # The link that RMG-models made irreversible keeps no REV.
        self.assertIsNone(self.link(self.model, (-1, "HO2"), (-1, "OH"), (1, "H2O"), (1, "O2")).reverse_rate)

    def test_the_rev_belongs_to_the_model_not_to_the_rate(self):
        species = ((-1, "H"), (-1, "O2"), (1, "O"), (1, "OH"))
        mine, other = self.link(self.model, *species), self.link(self.plain, *species)
        self.assertEqual(mine.kinetics_id, other.kinetics_id)
        self.assertIsNone(other.reverse_rate)

    def chemkin_blocks(self, model):
        """sides -> the entries of that reaction in the model's CHEMKIN export."""
        files = exports._generate_chemkin_files(model)
        (text,) = [v.decode() for k, v in files.items() if k.endswith("_chem.inp")]
        blocks = re.split(r"^(?=[^!\s]\S*=)", text.split("REACTIONS", 1)[1], flags=re.M)[1:]
        found = {}
        for block in blocks:
            found.setdefault(sides(block.split()[0]), []).append(block)
        return found

    def test_chemkin_export_writes_the_rev(self):
        blocks = self.chemkin_blocks(self.model)
        (block,) = blocks[sides("H + O2 <=> O + OH")]
        self.assertIn("REV / 7.04e+13 -0.26 0.15 /", block)
        # A DUPLICATE pair: one entry per line, each with its own REV or none.
        first, second = blocks[sides("O + H2 <=> H + OH")]
        self.assertIn("REV / 2e+12 0 5 /", first)
        self.assertNotIn("REV", second)
        self.assertIn("DUPLICATE", first)
        self.assertIn("DUPLICATE", second)
        self.assertIn("REV / 3e+19 -1 49 /", blocks[sides("H + O2 + M <=> HO2 + M")][0])
        self.assertIn("REV / 1.233e+66 -14.2349 63.0464 /", blocks[sides("H2O2 (+M) <=> OH + OH (+M)")][0])
        self.assertNotIn("REV", blocks[sides("HO2 + H <=> H2 + O2")][0])
        self.assertNotIn("REV", blocks[sides("HO2 + OH => H2O + O2")][0])
        self.assertNotIn("REV", "".join(b for bs in self.chemkin_blocks(self.plain).values() for b in bs))

    def test_rewriting_without_rev_changes_nothing(self):
        from rmgpy.chemkin import save_chemkin_file
        from rmgpy.reaction import Reaction
        from rmgpy.species import Species
        from rmgpy.thermo import NASA, NASAPolynomial
        from rmgpy.transport import TransportData

        species_map, _ = exports._build_rmg_species_map(self.model, NASAPolynomial, NASA, TransportData, Species)
        reactions = exports._build_rmg_reactions(self.model, species_map, Reaction)
        path = os.path.join(self.directory, "same.inp")
        save_chemkin_file(path, list(species_map.values()), reactions, verbose=False, check_for_duplicates=False)
        with open(path) as handle:
            before = handle.read()
        self.assertEqual(exports._write_reverse_rates(before, reactions, {}), before)

    def test_rev_is_added_to_the_entries_as_written(self):
        from rmgpy.chemkin import save_chemkin_file
        from rmgpy.reaction import Reaction
        from rmgpy.species import Species
        from rmgpy.thermo import NASA, NASAPolynomial
        from rmgpy.transport import TransportData

        species_map, _ = exports._build_rmg_species_map(self.model, NASAPolynomial, NASA, TransportData, Species)
        reverse = {}
        reactions = exports._build_rmg_reactions(self.model, species_map, Reaction, reverse=reverse)
        path = os.path.join(self.directory, "digits.inp")
        save_chemkin_file(path, list(species_map.values()), reactions, verbose=False, check_for_duplicates=False)
        with open(path) as handle:
            text = handle.read()
        # Another rewrite of the entries (more digits) stays as it is.
        self.assertIn("3.520000e+16", text)
        text = exports._write_reverse_rates(text.replace("3.520000e+16", "35200000000000000"), reactions, reverse)
        lines = text.splitlines()
        (number,) = [i for i, line in enumerate(lines) if "35200000000000000" in line]
        self.assertEqual(lines[number + 1].strip(), "REV / 7.04e+13 -0.26 0.15 /")
        # A file whose entries are not the reactions' is refused, not given misplaced REVs.
        with self.assertRaises(exports.ExportError):
            exports._write_reverse_rates("\n".join(l for l in lines if "35200000000000000" not in l), reactions, reverse)

    def test_cantera_export_runs_the_models_reverse_rate(self):
        result = exports.build_cantera_yaml(self.model)
        path = os.path.join(self.directory, "rev.yaml")
        with open(path, "wb") as handle:
            handle.write(result.content)
        gas = ct.Solution(path)
        gas.TP = 1000.0, ct.one_atm
        rates = {}
        for i, reaction in enumerate(gas.reactions()):
            rates.setdefault((sides(reaction.equation), reaction.reversible), []).append(gas.forward_rate_constants[i])
        # H + O2 <=> O + OH with REV: H + O2 => O + OH and O + OH => H + O2 at the REV rate.
        (forward,) = rates[(sides("H + O2 <=> O + OH"), False)]
        (backward,) = rates[(sides("O + OH <=> H + O2"), False)]
        rev = 7.04e13 * 1000 ** -0.26 * math.exp(-150.0 * 4.184 / (8.314462618 * 1000)) / 1e3   # m3/kmol/s
        self.assertAlmostEqual(backward / rev, 1.0, places=4)
        self.assertNotIn((sides("H + O2 <=> O + OH"), True), rates)
        # A reaction without REV stays reversible.
        self.assertIn((sides("HO2 + H <=> H2 + O2"), True), rates)
        self.assertGreater(forward, 0)

    def test_command_dry_run_apply_and_report(self):
        db.KineticsComment.objects.filter(kinetic_model=self.model).update(reverse_rate=None)
        report = os.path.join(self.directory, "reverse.csv")
        call_command("import_explicit_reverse_rates", "--path", self.directory, "--model", "rev",
                     "--report", report, stdout=open(os.devnull, "w"))
        self.assertFalse(db.KineticsComment.objects.filter(kinetic_model=self.model, reverse_rate__isnull=False).exists())
        call_command("import_explicit_reverse_rates", "--path", self.directory, "--model", "rev", "--apply",
                     "--report", report, stdout=open(os.devnull, "w"))
        self.assertEqual(db.KineticsComment.objects.filter(kinetic_model=self.model, reverse_rate__isnull=False).count(), 4)
        with open(report) as handle:
            status = {int(row["line"]): row["status"] for row in csv.DictReader(handle)}
        self.assertEqual(status, {4: "matched", 6: "matched", 11: "matched", 13: "matched",
                                  20: "irreversible_link", 22: "no_species"})
        # Again: nothing to change (PostgreSQL gives 1.233e66 back as an integer).
        result = explicit_reverse.attach(self.model, os.path.join(self.directory, "rev"), MODELS)
        self.assertEqual((result["set"], result["cleared"], result["unchanged"]), (0, 0, 4))
