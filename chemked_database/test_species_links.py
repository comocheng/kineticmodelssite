"""Links from ChemKED mixture components to species records (chemked_database.species_links).

The records keep RMG's augmented InChI and ChemKED gives standard InChIs, so a standard InChI
can match records of several spins; the component is the ground state. Kept apart from
tests.py, which needs pyked.batch_convert.
"""

from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from database import models as dm

from .models import Composition, CompositionSpecies, ExperimentDataset
from .species_links import NO_RECORD, SEVERAL_SPINS, SpeciesLinker, standard_inchi

TESTDATA = Path(__file__).resolve().parent / "testdata"


def make_species(inchi, adjacency_list, electronic_state="", formula=None):
    """A species record with one isomer and one structure, as the RMG importer stores them."""
    formula, _ = dm.Formula.objects.get_or_create(formula=formula or inchi.split("/")[1])
    isomer, _ = dm.Isomer.objects.get_or_create(inchi=inchi, formula=formula)
    if not dm.Structure.objects.filter(adjacency_list=adjacency_list).exists():
        dm.Structure.objects.create(
            isomer=isomer, adjacency_list=adjacency_list,
            multiplicity=int(adjacency_list.split()[1]) if adjacency_list.startswith("multiplicity") else 1,
        )
    species = dm.Species.objects.create(hash=f"{inchi}@{electronic_state}", electronic_state=electronic_state)
    species.isomers.add(isomer)
    return species


class SpeciesRecords(TestCase):
    """Records of several spins for O2, CO, N2O, O and CH2. Where the database has the ground
    state second, it is made second here too, so the lower id is never the reason a record wins."""

    @classmethod
    def setUpTestData(cls):
        cls.o2_singlet = make_species("InChI=1S/O2/c1-2", "1 O u0 p2 c0 {2,D}\n2 O u0 p2 c0 {1,D}")
        cls.o2 = make_species("InChI=1S/O2/c1-2/u1,2", "multiplicity 3\n1 O u1 p2 c0 {2,S}\n2 O u1 p2 c0 {1,S}")
        cls.co_triplet = make_species("InChI=1S/CO/c1-2/u1,1", "multiplicity 3\n1 C u2 p0 c0 {2,D}\n2 O u0 p2 c0 {1,D}")
        cls.co = make_species("InChI=1S/CO/c1-2/lp1,2", "1 C u0 p1 c-1 {2,T}\n2 O u0 p1 c+1 {1,T}")
        cls.n2o_triplet = make_species(
            "InChI=1S/N2O/c1-2-3/u1,1", "multiplicity 3\n1 O u0 p2 c0 {2,D}\n2 N u0 p1 c0 {1,D} {3,S}\n3 N u2 p1 c0 {2,S}")
        cls.n2o = make_species(
            "InChI=1S/N2O/c1-2-3/lp1,1,1(0)", "1 N u0 p2 c-1 {2,D}\n2 N u0 p0 c+1 {1,D} {3,D}\n3 O u0 p2 c0 {2,D}")
        cls.o_singlet = make_species("InChI=1S/O/lp1,1,1", "1 O u0 p3 c0")
        cls.o = make_species("InChI=1S/O/u1,1", "multiplicity 3\n1 O u2 p2 c0")
        cls.ch2 = make_species(
            "InChI=1S/CH2/h1H2/u1,1", "multiplicity 3\n1 C u2 p0 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}")
        cls.ch2_singlet = make_species(
            "InChI=1S/CH2/h1H2/lp1", "1 C u0 p1 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}")
        cls.oh = make_species("InChI=1S/HO/h1H/u1", "multiplicity 2\n1 O u1 p2 c0 {2,S}\n2 H u0 p0 c0 {1,S}")
        cls.oh_excited = make_species(
            "InChI=1S/HO/h1H/u1", "multiplicity 2\n1 O u1 p2 c0 {2,S}\n2 H u0 p0 c0 {1,S}", electronic_state="excited")
        cls.h2 = make_species("InChI=1S/H2/h1H", "1 H u0 p0 c0 {2,S}\n2 H u0 p0 c0 {1,S}")
        # A record whose isomer has no InChI is found by the InChIKey of its structure.
        cls.ch4 = make_species("", "1 C u0 p0 c0 {2,S} {3,S} {4,S} {5,S}\n2 H u0 p0 c0 {1,S}\n"
                               "3 H u0 p0 c0 {1,S}\n4 H u0 p0 c0 {1,S}\n5 H u0 p0 c0 {1,S}", formula="CH4")


class StandardInchiTests(SimpleTestCase):
    def test_prefix_is_added(self):
        self.assertEqual(standard_inchi("1S/O2/c1-2"), "InChI=1S/O2/c1-2")
        self.assertEqual(standard_inchi(" InChI=1S/O "), "InChI=1S/O")

    def test_rmg_layers_are_dropped(self):
        self.assertEqual(standard_inchi("InChI=1S/O2/c1-2/u1,2"), "InChI=1S/O2/c1-2")
        self.assertEqual(standard_inchi("InChI=1S/N2O/c1-2-3/lp1(0),3,3,3"), "InChI=1S/N2O/c1-2-3")
        self.assertEqual(standard_inchi("InChI=1S/N2O/c1-2-3/u1,2/lp1,1,1(0)"), "InChI=1S/N2O/c1-2-3")
        self.assertEqual(standard_inchi("InChI=1S/C3H5/c1-3-2/h3H,1-2H2/u1,2"), "InChI=1S/C3H5/c1-3-2/h3H,1-2H2")

    def test_empty(self):
        self.assertEqual(standard_inchi(""), "")
        self.assertEqual(standard_inchi(None), "")


class SpeciesLinkerTests(SpeciesRecords):
    def setUp(self):
        self.linker = SpeciesLinker()

    def test_o2_is_triplet_o2(self):
        # The standard InChI of O2 is exactly the singlet record's InChI.
        self.assertEqual(self.linker.resolve("1S/O2/c1-2"), (self.o2.pk, "ground state"))

    def test_co_and_n2o_are_singlets(self):
        self.assertEqual(self.linker.species_id("1S/CO/c1-2"), self.co.pk)
        self.assertEqual(self.linker.species_id("InChI=1S/N2O/c1-2-3"), self.n2o.pk)

    def test_atomic_oxygen_is_triplet(self):
        self.assertEqual(self.linker.species_id("1S/O"), self.o.pk)

    def test_one_record_is_linked(self):
        self.assertEqual(self.linker.resolve("1S/H2/h1H"), (self.h2.pk, "standard InChI"))

    def test_record_with_rmg_layers_is_found(self):
        self.assertEqual(self.linker.species_id("1S/HO/h1H"), self.oh.pk)

    def test_excited_state_is_never_linked(self):
        self.assertNotEqual(self.linker.species_id("1S/HO/h1H"), self.oh_excited.pk)

    def test_several_spins_without_a_ground_state_give_no_link(self):
        self.assertEqual(self.linker.resolve("1S/CH2/h1H2"), (None, SEVERAL_SPINS))

    def test_unknown_species_gives_no_link(self):
        self.assertEqual(self.linker.resolve("1S/Ar"), (None, NO_RECORD))

    def test_inchikey_fallback(self):
        self.assertEqual(self.linker.resolve("1S/CH4/h1H4"), (self.ch4.pk, "InChIKey"))

    def test_prefix_of_another_formula_is_not_a_match(self):
        # "InChI=1S/O" is the start of the InChI of O2.
        self.assertNotIn(self.linker.species_id("1S/O"), {self.o2.pk, self.o2_singlet.pk})


class BackfillCompositionSpeciesLinksTests(SpeciesRecords):
    def setUp(self):
        composition = Composition.objects.create(kind="mole fraction")

        def row(name, inchi, link=None):
            return CompositionSpecies.objects.create(
                composition=composition, species_name=name, inchi=inchi, amount=0.1, database_species=link)

        self.o2_row = row("O2", "1S/O2/c1-2", self.o2_singlet)  # linked by the earlier rule
        self.co_row = row("CO", "1S/CO/c1-2")
        self.ch2_row = row("CH2", "1S/CH2/h1H2", self.ch2)
        self.h2_row = row("H2", "1S/H2/h1H", self.h2)
        self.no_inchi_row = row("O2", "", self.o2_singlet)

    def _backfill(self, *args):
        out = StringIO()
        call_command("backfill_composition_species_links", *args, stdout=out)
        for r in (self.o2_row, self.co_row, self.ch2_row, self.h2_row, self.no_inchi_row):
            r.refresh_from_db()
        return out.getvalue()

    def test_links_agree_with_the_inchi(self):
        out = self._backfill()

        self.assertEqual(self.o2_row.database_species, self.o2)
        self.assertEqual(self.co_row.database_species, self.co)
        self.assertIsNone(self.ch2_row.database_species)
        self.assertEqual(self.h2_row.database_species, self.h2)
        self.assertIn("1 linked, 1 moved to another record, 1 unlinked, 1 unchanged", out)

    def test_row_without_inchi_is_left_alone(self):
        self._backfill()
        self.assertEqual(self.no_inchi_row.database_species, self.o2_singlet)

    def test_dry_run_writes_nothing(self):
        out = self._backfill("--dry-run")
        self.assertEqual(self.o2_row.database_species, self.o2_singlet)
        self.assertIsNone(self.co_row.database_species)
        self.assertIn("[dry-run]", out)

    def test_second_run_changes_nothing(self):
        self._backfill()
        out = self._backfill()
        self.assertIn("0 linked, 0 moved to another record, 0 unlinked, 4 unchanged", out)


class SyncChemkedLinksTests(SpeciesRecords):
    def test_components_are_linked_at_ingest(self):
        call_command("sync_chemked", path=str(TESTDATA), files=["Test_2020_ST_7.yaml"],
                     stdout=StringIO(), stderr=StringIO())

        self.assertTrue(ExperimentDataset.objects.filter(chemked_file_path="Test_2020_ST_7.yaml").exists())
        links = {(cs.species_name, cs.database_species_id) for cs in CompositionSpecies.objects.all()}
        self.assertEqual(links, {("H2", self.h2.pk), ("O2", self.o2.pk), ("Ar", None)})
