import io
import json
import tempfile
import os
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from rmgpy.molecule import Molecule
from rmgpy.thermo import NASA, NASAPolynomial

from database import models
from database.services import thermo_sources as sources


METHANE = {
    "ATcT_TN_Version": "1.220", "ATcT_ID": "74-82-8*0", "Name": "Methane",
    "Formula": "CH4  (g)", "∆fH_0K": "-66.543", "∆fH_298K": "-74.513",
    "∆fH_298K_uncertainty": "0.043", "units": "kJ/mol", "SMILES": "C",
    "CASRN": "74-82-8", "InChI": "InChI=1S/CH4/h1H4", "charge": 0,
}


def import_methane(**changes):
    return sources.import_atct(dict(METHANE, **changes), multiplicity=1, electronic_state="ground state")


def nasa_fixture():
    return NASA(polynomials=[
        NASAPolynomial(coeffs=[4, 0, 0, 0, 0, -10000, 1], Tmin=(200, "K"), Tmax=(1000, "K")),
        NASAPolynomial(coeffs=[4, 0, 0, 0, 0, -10000, 1], Tmin=(1000, "K"), Tmax=(3000, "K")),
    ], Tmin=(200, "K"), Tmax=(3000, "K"))


class ATcTRecordTests(TestCase):
    def test_units_identity_and_enthalpy_only(self):
        record = import_methane()
        self.assertAlmostEqual(record.enthalpy_298, -74513)
        self.assertAlmostEqual(record.enthalpy_0, -66543)
        self.assertAlmostEqual(record.uncertainty_298, 43)
        self.assertIsNone(record.nasa_thermo_id)
        self.assertIsNone(record.entropy_298)
        self.assertEqual(record.structure.isomer.formula.formula, "CH4")
        self.assertEqual(record.raw_data, METHANE)
        self.assertEqual(models.Thermo.objects.count(), 0)

    def test_repeat_import_and_version_history(self):
        first = import_methane()
        self.assertEqual(import_methane().pk, first.pk)
        second = import_methane(ATcT_TN_Version="1.221")
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.structure_id, second.structure_id)
        self.assertEqual(models.Species.objects.count(), 1)
        self.assertEqual(models.SpeciesName.objects.count(), 1)

    def test_reject_incomplete_mismatched_condensed_and_nonfinite(self):
        for changes in [
            {"Formula": "CH4 (l)"}, {"SMILES": "CC"}, {"charge": 1},
            {"units": "unknown"}, {"∆fH_298K": "NaN"}, {"∆fH_298K_uncertainty": "-1"},
            {"ATcT_TN_Version": ""}, {"SMILES": ""}, {"InChI": "wrong"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(sources.ThermoSourceError):
                import_methane(**changes)
        self.assertEqual(models.ThermoRecord.objects.count(), 0)
        self.assertEqual(models.Species.objects.count(), 0)

    def test_zero_uncertainty_is_preserved(self):
        self.assertEqual(import_methane(**{"∆fH_298K_uncertainty": "0"}).uncertainty_298, 0)

    def test_linked_structure_identity_cannot_be_reassigned(self):
        from django.core.exceptions import ValidationError
        structure = import_methane().structure
        structure.smiles = "CC"
        with self.assertRaises(ValidationError):
            structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.smiles, "C")
        structure.iupac_name = "methane"
        structure.save(update_fields=["iupac_name"])

    def test_no_isotope_identity_loss(self):
        isotope = dict(METHANE, SMILES="[13CH4]", InChI="")
        with self.assertRaisesRegex(sources.ThermoSourceError, "isotopic"):
            sources.import_atct(isotope, multiplicity=1, electronic_state="ground state")

    def test_spin_requires_review_and_agreement(self):
        for multiplicity, state in [(3, "ground state"), (1, ""), (0, "ground state")]:
            with self.assertRaises(sources.ThermoSourceError):
                sources.import_atct(METHANE, multiplicity=multiplicity, electronic_state=state)

    @patch.object(sources, "fetch_atct", return_value=METHANE)
    def test_command_dry_run(self, fetch):
        # The command imports its client symbol directly.
        with patch("database.management.commands.import_atct_thermo.fetch_atct", return_value=METHANE):
            call_command("import_atct_thermo", atct_id="74-82-8*0", multiplicity=1,
                         state_label="ground state", dry_run=True, stdout=io.StringIO())
        self.assertFalse(models.ThermoRecord.objects.exists())
        self.assertFalse(models.Species.objects.exists())

    def test_source_cannot_change_structure_in_same_version(self):
        original = import_methane()
        with self.assertRaises(sources.ThermoSourceError):
            sources.save_record(Molecule().from_smiles("CC"), provider="atct", external_id=original.external_id,
                                source_version=original.source_version, label="Ethane")
        self.assertEqual(models.Species.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.label, "Methane")

    def test_offline_snapshot_requires_exact_id_and_retains_provenance(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as snapshot:
            json.dump(METHANE, snapshot)
            snapshot.flush()
            with patch("database.management.commands.import_atct_thermo.fetch_atct") as fetch:
                with self.assertRaisesRegex(CommandError, "exact requested"):
                    call_command("import_atct_thermo", atct_id="different", multiplicity=1,
                                 state_label="ground state", input_file=snapshot.name, stdout=io.StringIO())
                self.assertFalse(models.ThermoRecord.objects.exists())
                call_command("import_atct_thermo", atct_id="74-82-8*0", multiplicity=1,
                             state_label="ground state", input_file=snapshot.name, stdout=io.StringIO())
                fetch.assert_not_called()
        self.assertIn("previously retrieved API JSON snapshot", models.ThermoRecord.objects.get().provenance)

    def test_display_and_readonly_api(self):
        record = import_methane(**{"Name": "<script>bad</script>", "∆fH_298K_uncertainty": "0"})
        response = self.client.get(reverse("species-detail", args=[record.species_id]))
        self.assertContains(response, "ATcT")
        self.assertContains(response, "Reference enthalpy only")
        self.assertContains(response, "± 0.00")
        self.assertContains(response, "&lt;script&gt;bad&lt;/script&gt;")
        self.assertNotContains(response, "<script>bad</script>")
        url = reverse("api-thermo-record-list")
        response = self.client.get(url, {"provider": "atct"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["enthalpy_298"], -74513)
        self.assertIn(self.client.post(url, {}).status_code, (401, 403, 405))

    def test_sidebar_names_models_that_supplied_thermo(self):
        species, _ = sources._species_and_structure(Molecule().from_smiles("C"), "Methane")
        thermo = models.Thermo.objects.create(species=species, reference_temp=298.15, **sources.nasa_fields(nasa_fixture()))
        for name in ("GRI-Mech 3.0", "AramcoMech 2.0"):
            models.ThermoComment.objects.create(thermo=thermo, kinetic_model=models.KineticModel.objects.create(model_name=name))
        response = self.client.get(reverse("species-detail", args=[species.pk]))
        self.assertContains(response, "GRI-Mech 3.0 + 1 more")
        self.assertContains(response, 'title="GRI-Mech 3.0, AramcoMech 2.0"')
        self.assertNotContains(response, "Imported model thermo")

    def test_same_formula_isomers_remain_separate(self):
        ethanol = dict(METHANE, ATcT_ID="ethanol", Name="Ethanol", Formula="C2H6O (g)", SMILES="CCO", InChI="")
        ether = dict(ethanol, ATcT_ID="ether", Name="Dimethyl ether", SMILES="COC")
        a = sources.import_atct(ethanol, multiplicity=1, electronic_state="ground state")
        b = sources.import_atct(ether, multiplicity=1, electronic_state="ground state")
        self.assertNotEqual(a.species_id, b.species_id)
        self.assertNotEqual(a.structure.isomer_id, b.structure.isomer_id)
        page = self.client.get(reverse("species-detail", args=[a.species_id]))
        self.assertContains(page, "Ethanol")
        self.assertNotContains(page, "Dimethyl ether")


class NASARecordTests(TestCase):
    def test_polynomial_provenance_and_idempotency(self):
        molecule = Molecule().from_smiles("C")
        kwargs = dict(provider="burcat", external_id="test:methane", source_version="test",
                      label="Methane", nasa=nasa_fixture(), enthalpy_298=-73000)
        first = sources.save_record(molecule, **kwargs)
        second = sources.save_record(molecule, **kwargs)
        self.assertEqual(first.nasa_thermo_id, second.nasa_thermo_id)
        self.assertEqual(models.Thermo.objects.count(), 1)
        self.assertAlmostEqual(first.nasa_thermo.enthalpy298, kwargs["nasa"].get_enthalpy(298.15))
        page = self.client.get(reverse("thermo-detail", args=[first.nasa_thermo_id]))
        self.assertContains(page, "Burcat")
        self.assertContains(page, "Source record and provenance")

    def test_invalid_polynomial_rolls_back_species_creation(self):
        bad = nasa_fixture()
        bad.polynomials[1].Tmin = (1100, "K")
        with self.assertRaises(sources.ThermoSourceError):
            sources.save_record(Molecule().from_smiles("C"), provider="burcat", external_id="bad",
                                source_version="test", label="Bad", nasa=bad)
        self.assertFalse(models.Species.objects.exists())
        self.assertFalse(models.ThermoRecord.objects.exists())


class ATcTConstrainedTests(TestCase):
    def heat_capacity_source(self, provider="group_additivity"):
        return sources.save_record(Molecule().from_smiles("C"), provider=provider, external_id="methane-estimate",
                                   source_version="v1", label="methane", nasa=nasa_fixture(), enthalpy_298=-73000)

    def test_enthalpy_moves_while_heat_capacity_and_entropy_stay(self):
        atct = import_methane()
        source = self.heat_capacity_source()
        [derived] = sources.derive_atct_constrained(atct)
        thermo, original = derived.nasa_thermo, source.nasa_thermo
        self.assertAlmostEqual(thermo.enthalpy298, -74513, delta=1)
        for temp in (300, 1500, 2900):
            self.assertAlmostEqual(thermo.heat_capacity(temp), original.heat_capacity(temp))
            self.assertAlmostEqual(thermo.entropy(temp), original.entropy(temp))
        self.assertEqual((derived.enthalpy_source, derived.heat_capacity_source), (atct, source))
        self.assertEqual(derived.get_provider_display(), "ATcT-constrained RMG thermo")
        # The ATcT uncertainty belongs to the 298.15 K enthalpy, not to the whole polynomial.
        self.assertIsNone(derived.uncertainty_298)
        self.assertIn("does not establish the accuracy of Cp(T)", derived.provenance)
        self.assertEqual(sources.derive_atct_constrained(atct)[0].pk, derived.pk)
        page = self.client.get(reverse("species-detail", args=[atct.species_id]))
        self.assertContains(page, "ATcT-constrained RMG thermo")
        self.assertContains(page, f'Cp and S from <a href="{reverse("thermo-detail", args=[source.nasa_thermo_id])}">Group Additivity</a>')
        # How far the source's own enthalpy was from ATcT tells the reader how much to trust its Cp and S.
        shift = (-74513 - original.enthalpy298) / 1000
        self.assertAlmostEqual(derived.enthalpy_shift_kj, shift, places=3)
        self.assertContains(page, f"its H298 moved {shift:.1f} kJ/mol")

    def test_nothing_derived_without_heat_capacity_source(self):
        self.assertEqual(sources.derive_atct_constrained(import_methane()), [])
        self.assertFalse(models.ThermoRecord.objects.filter(provider="atct_constrained").exists())

    def test_backfill_command_reports_and_dry_run_saves_nothing(self):
        import_methane()
        self.heat_capacity_source(provider="burcat")
        out = io.StringIO()
        call_command("derive_atct_thermo", dry_run=True, stdout=out)
        self.assertIn("derived records: 1", out.getvalue())
        self.assertFalse(models.ThermoRecord.objects.filter(provider="atct_constrained").exists())
        call_command("derive_atct_thermo", stdout=io.StringIO())
        self.assertEqual(models.ThermoRecord.objects.filter(provider="atct_constrained").count(), 1)


@override_settings(ATCT_API_BASE_URL="https://atct.example/api/v1", ATCT_API_KEY="test-key")
class ATcTClientTests(SimpleTestCase):
    @patch.object(sources.requests, "Session")
    def test_exact_id_and_bearer_header(self, session_class):
        session = session_class.return_value.__enter__.return_value
        session.headers = {}
        session.get.return_value.json.return_value = [METHANE]
        self.assertEqual(sources.fetch_atct("74-82-8*0"), METHANE)
        self.assertEqual(session.headers["Authorization"], "Bearer test-key")
        self.assertEqual(session.get.call_args.kwargs["params"], {"atctid": "74-82-8*0"})
        session.get.return_value.json.return_value = [METHANE, METHANE]
        with self.assertRaises(sources.ThermoSourceError):
            sources.fetch_atct("74-82-8*0")
        session.get.return_value.json.return_value = METHANE
        with self.assertRaises(sources.ThermoSourceError):
            sources.fetch_atct("different")


class GroupAdditivityTests(TestCase):
    def test_electronic_term_symbol_is_not_discarded(self):
        record = import_methane()
        record.structure.adjacency_list = "molecularTermSymbol 1A1\n" + record.structure.adjacency_list
        with self.assertRaisesRegex(sources.ThermoSourceError, "term symbols"):
            sources.estimate_groups(record.structure, Mock(), "test")

    def test_symmetry_correction_and_fit_provenance(self):
        from rmgpy.thermo import ThermoData
        from rmgpy.constants import R
        import math
        record = import_methane()
        data = ThermoData(Tdata=([300, 400, 500, 600, 800, 1000, 1500], "K"),
                          Cpdata=([36, 40, 47, 53, 64, 73, 86], "J/(mol*K)"),
                          H298=(-74500, "J/mol"), S298=(207, "J/(mol*K)"),
                          Cp0=(33.26, "J/(mol*K)"), CpInf=(108.08, "J/(mol*K)"), comment="fixture group")
        database = Mock()
        database.get_thermo_data_from_groups.return_value = data
        estimate = sources.estimate_groups(record.structure, database, "sha256:test")
        self.assertAlmostEqual(estimate.raw_data["S298_J_mol_K"], 207 - R * math.log(12))
        self.assertEqual(estimate.provider, "group_additivity")
        self.assertIsNotNone(estimate.nasa_thermo_id)
        self.assertLess(estimate.raw_data["fit_max_relative_cp_error"], 0.05)
        self.assertIn("fixture group", estimate.provenance)
        self.assertIsNone(estimate.uncertainty_298)

    def test_bad_fit_is_not_saved(self):
        record = import_methane()
        database = Mock()
        data = database.get_thermo_data_from_groups.return_value
        data.Tdata.value_si = [300]
        data.Cpdata.value_si = [10000]
        data.to_nasa.return_value = nasa_fixture()
        data.get_enthalpy.return_value = 0
        data.get_entropy.return_value = 0
        data.S298.value_si = 200
        with self.assertRaisesRegex(sources.ThermoSourceError, "fit failed"):
            sources.estimate_groups(record.structure, database, "test")
        self.assertEqual(models.ThermoRecord.objects.count(), 1)


@skipUnless(os.getenv("KMS_THERMO_TEST_DATABASE"), "Set KMS_THERMO_TEST_DATABASE to exercise real RMG data")
class RealRMGIntegrationTests(TestCase):
    def test_burcat_import_and_propane_estimate(self):
        path = os.environ["KMS_THERMO_TEST_DATABASE"]
        call_command("import_burcat_thermo", database_path=path, limit=2, stdout=io.StringIO())
        call_command("import_burcat_thermo", database_path=path, limit=2, stdout=io.StringIO())
        self.assertEqual(models.ThermoRecord.objects.filter(provider="burcat").count(), 2)
        _, structure = sources._species_and_structure(Molecule().from_smiles("CCC"), "Propane")
        call_command("estimate_species_thermo", database_path=path, structure_id=[structure.pk], stdout=io.StringIO())
        record = models.ThermoRecord.objects.get(provider="group_additivity")
        self.assertLess(record.raw_data["fit_max_relative_cp_error"], 0.05)
        self.assertAlmostEqual(record.enthalpy_298, -105969.56, delta=5000)
        self.assertEqual(models.Thermo.objects.count(), 3)
