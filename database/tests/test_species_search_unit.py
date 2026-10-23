import io
from html import unescape
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from database.filters import SpeciesFilter
from database.models import Formula, Isomer, Species, SpeciesName, Structure, StructureName
from database.services.chemical_identity import canonical_smiles, normalize_formula
from database.services.pubchem import PubChemClient, PubChemError


class ChemicalIdentityTests(SimpleTestCase):
    def test_equivalent_smiles(self):
        self.assertEqual(canonical_smiles("OCC"), canonical_smiles("CCO"))
        self.assertEqual(canonical_smiles("[CH3:1][OH:2]"), canonical_smiles("CO"))

    def test_distinct_isomers_stereo_isotopes_and_radicals(self):
        for left, right in [("CCO", "COC"), ("F/C=C/F", "F/C=C\\F"),
                            ("[13CH4]", "C"), ("[CH3]", "C"),
                            ("C[C@H](O)F", "C[C@@H](O)F")]:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(canonical_smiles(left), canonical_smiles(right))

    def test_invalid_smiles_and_trailing_names(self):
        for value in ["methane", "C methane", "invalid[", "", "C" * 501]:
            self.assertIsNone(canonical_smiles(value))

    def test_formula_normalization(self):
        self.assertEqual(normalize_formula("CH₄"), "CH4")
        self.assertEqual(normalize_formula("H6C2O"), "C2H6O")
        for value in ["CCO", "methane", "C0H4", "Xx2", "C(=O)O"]:
            self.assertIsNone(normalize_formula(value))


class SpeciesSearchTests(TestCase):
    @classmethod
    def add_species(cls, name, formula, smiles, inchi, **fields):
        formula, _ = Formula.objects.get_or_create(formula=formula)
        isomer = Isomer.objects.create(formula=formula, inchi=inchi)
        species = Species.objects.create(hash=name, **fields)
        species.isomers.add(isomer)
        structure = Structure.objects.create(
            isomer=isomer, smiles=smiles, adjacency_list=f"fixture {name}",
            multiplicity=1, iupac_name=name,
        )
        return species, structure

    @classmethod
    def setUpTestData(cls):
        cls.methane, cls.methane_structure = cls.add_species(
            "methane", "CH4", "C", "InChI=1S/CH4/h1H4",
            prime_id="s00000001", cas_number="74-82-8",
        )
        cls.ethanol, cls.ethanol_structure = cls.add_species(
            "ethanol", "C2H6O", "CCO", "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
        )
        cls.ether, cls.ether_structure = cls.add_species(
            "methoxymethane", "C2H6O", "COC", "InChI=1S/C2H6O/c1-3-2/h1-2H3",
        )
        cls.chloro, _ = cls.add_species(
            "chloromethane", "CH3Cl", "CCl", "InChI=1S/CH3Cl/c1-2/h1H3",
        )
        StructureName.objects.create(structure=cls.ethanol_structure, name="ethyl alcohol")
        SpeciesName.objects.create(species=cls.ethanol, name="C2H5OH")
        SpeciesName.objects.create(species=cls.ethanol, name="C2H5OH")

    def results(self, value):
        search = SpeciesFilter({"q": value}, queryset=Species.objects.order_by("id"))
        self.assertTrue(search.is_valid(), search.errors)
        return list(search.qs.values_list("pk", flat=True))

    def test_methane_name_formula_identifiers_and_structure(self):
        for value in ["methane", "METHANE", " CH4 ", "CH₄", "smiles:C", "74-82-8",
                      "s00000001", str(self.methane.pk), "InChI=1S/CH4/h1H4"]:
            with self.subTest(value=value):
                self.assertEqual(self.results(value), [self.methane.pk])

    def test_formula_finds_all_isomers(self):
        for value in ["C2H6O", "H6C2O", "formula:C2H6O"]:
            self.assertEqual(self.results(value), [self.ethanol.pk, self.ether.pk])

    def test_specific_name_or_smiles_does_not_expand_formula(self):
        for value in ["ethanol", "ethyl alcohol", "CCO", "OCC", "smiles:CCO", "C2H5OH"]:
            with self.subTest(value=value):
                self.assertEqual(self.results(value), [self.ethanol.pk])
        self.assertEqual(self.results("COC"), [self.ether.pk])

    def test_exact_name_does_not_match_larger_names(self):
        self.assertEqual(self.results("methane"), [self.methane.pk])

    def test_partial_names_and_no_duplicate_species(self):
        self.assertEqual(self.results("ethyl alco"), [self.ethanol.pk])
        self.assertEqual(self.results("C2H5OH"), [self.ethanol.pk])

    def test_structure_and_isomer_ids(self):
        self.assertEqual(self.results(f"structure:{self.ether_structure.pk}"), [self.ether.pk])
        self.assertEqual(self.results(f"isomer:{self.ether_structure.isomer_id}"), [self.ether.pk])

    def test_ambiguous_formula_can_be_overridden(self):
        methanol, _ = self.add_species("methanol", "CH4O", "CO", "methanol-fixture")
        carbon_monoxide, _ = self.add_species("carbon monoxide", "CO", "[C-]#[O+]", "co-fixture")
        self.assertEqual(self.results("CO"), [carbon_monoxide.pk])
        self.assertEqual(self.results("smiles:CO"), [methanol.pk])

    def test_empty_unknown_and_invalid_queries(self):
        self.assertEqual(len(self.results("")), 4)
        for value in ["no-such-species", "smiles:invalid[", "id:abc", "id:" + "9" * 50]:
            self.assertEqual(self.results(value), [])

    def test_legacy_filter_urls(self):
        for data in [{"cas_number": "74-82-8"}, {"isomers": [self.methane_structure.isomer_id]},
                     {"isomers__structures": [self.methane_structure.pk]}]:
            search = SpeciesFilter(data, queryset=Species.objects.all())
            self.assertEqual(list(search.qs), [self.methane])

    def test_page_is_accessible_without_login_and_has_single_search_input(self):
        response = self.client.get(reverse("species-search"), {"q": "C2H6O"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="q"', count=1)
        self.assertNotContains(response, '<select')
        self.assertContains(response, "ethanol")
        self.assertContains(response, "methoxymethane")

    def test_page_query_count_does_not_grow_with_number_of_rows(self):
        with CaptureQueriesContext(connection) as single:
            self.client.get(reverse("species-search"), {"q": "CH4"})
        with CaptureQueriesContext(connection) as multiple:
            self.client.get(reverse("species-search"), {"q": "C2H6O"})
        self.assertEqual(len(single), len(multiple))
        self.assertLessEqual(len(multiple), 10)

    def test_pubchem_links_follow_species_structures_and_are_deduplicated(self):
        Structure.objects.filter(pk=self.ethanol_structure.pk).update(pubchem_cid=702)
        Structure.objects.filter(pk=self.ether_structure.pk).update(pubchem_cid=8254)
        Structure.objects.create(
            isomer=self.ethanol_structure.isomer, smiles="OCC", multiplicity=1,
            adjacency_list="duplicate ethanol representation", pubchem_cid=702,
        )
        self.ethanol.isomers.add(self.ether_structure.isomer)
        response = self.client.get(reverse("species-search"), {"q": "C2H6O"})
        mappings = {s.pk: s.search_pubchem_cids for s in response.context["object_list"]}
        self.assertEqual(mappings[self.ethanol.pk], [702, 8254])
        self.assertEqual(mappings[self.ether.pk], [8254])
        self.assertContains(response, 'href="https://pubchem.ncbi.nlm.nih.gov/compound/702"', count=1)
        self.assertContains(response, 'href="https://pubchem.ncbi.nlm.nih.gov/compound/8254"', count=2)
        unmatched = self.client.get(reverse("species-search"), {"q": "CH4"})
        self.assertContains(unmatched, "No linked record")
        self.assertNotContains(unmatched, "pubchem.ncbi.nlm.nih.gov/compound/")

    def test_pagination_preserves_query(self):
        with patch("database.views.SpeciesFilterView.cls.paginate_by", 1):
            response = self.client.get(reverse("species-search"), {"q": "C2H6O"})
            self.assertIn("q=C2H6O&page=2", unescape(response.content.decode()))
            second = self.client.get(reverse("species-search"), {"q": "C2H6O", "page": 2})
            self.assertEqual(list(second.context["object_list"]), [self.ether])


class PubChemTests(SimpleTestCase):
    def setUp(self):
        self.client = PubChemClient()
        self.client.session = Mock()

    def response(self, payload, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload
        return response

    @patch("database.services.pubchem.time.sleep")
    def test_resolves_names_and_sends_smiles_as_parameter(self, sleep):
        self.client.session.get.side_effect = [
            self.response({"PropertyTable": {"Properties": [
                {"CID": 297, "SMILES": "C", "IUPACName": "methane"}]}}),
            self.response({"InformationList": {"Information": [
                {"CID": 297, "Synonym": ["methane", "marsh gas", "methane"]}]}}),
        ]
        result = self.client.resolve("C")
        self.assertEqual(result["iupac_name"], "methane")
        self.assertEqual(result["synonyms"], ["marsh gas", "methane"])
        self.assertEqual(self.client.session.get.call_args_list[0].kwargs["params"], {"smiles": "C"})

    @patch("database.services.pubchem.time.sleep")
    def test_rejects_different_structure_even_with_same_formula(self, sleep):
        self.client.session.get.return_value = self.response({"PropertyTable": {"Properties": [
            {"CID": 8254, "SMILES": "COC", "IUPACName": "methoxymethane"}]}})
        self.assertIsNone(self.client.resolve("CCO"))
        self.assertEqual(self.client.session.get.call_count, 1)

    @patch("database.services.pubchem.time.sleep")
    def test_not_found_is_not_an_api_failure(self, sleep):
        self.client.session.get.return_value = self.response({}, status=404)
        self.assertIsNone(self.client.resolve("C"))

    @patch("database.services.pubchem.time.sleep")
    def test_timeout_is_retried_and_reported(self, sleep):
        self.client.session.get.side_effect = requests.Timeout()
        with self.assertRaisesRegex(PubChemError, "Timeout.*after 3 attempts"):
            self.client.resolve("C")
        self.assertEqual(self.client.session.get.call_count, 3)

    @patch("database.services.pubchem.time.sleep")
    def test_rate_limit_is_retried(self, sleep):
        self.client.session.get.side_effect = [self.response({}, 429), self.response({}, 404)]
        self.assertIsNone(self.client.resolve("C"))
        self.assertEqual(self.client.session.get.call_count, 2)

    @patch("database.services.pubchem.time.sleep")
    def test_malformed_response_is_not_cached_as_missing(self, sleep):
        self.client.session.get.return_value = self.response({})
        with self.assertRaises(PubChemError):
            self.client.resolve("C")

    @patch("database.services.pubchem.time.sleep")
    def test_compound_without_names_is_not_a_failed_lookup(self, sleep):
        # Actual response for local structure 26991: valid CID/SMILES, no IUPACName.
        self.client.session.get.side_effect = [
            self.response({"PropertyTable": {"Properties": [
                {"CID": 22750579, "SMILES": "CC(CC=C=O)O"}]}}),
            self.response({}, status=404),
        ]
        self.assertEqual(self.client.resolve("CC(O)CC=C=O"), {
            "cid": 22750579, "iupac_name": "", "synonyms": [],
        })

    @patch("database.services.pubchem.time.sleep")
    def test_synonyms_remain_searchable_when_iupac_name_is_missing(self, sleep):
        self.client.session.get.side_effect = [
            self.response({"PropertyTable": {"Properties": [{"CID": 297, "SMILES": "C"}]}}),
            self.response({"InformationList": {"Information": [
                {"CID": 297, "Synonym": ["marsh gas"]}]}}),
        ]
        result = self.client.resolve("C")
        self.assertEqual(result, {"cid": 297, "iupac_name": "", "synonyms": ["marsh gas"]})

    @patch("database.services.pubchem.time.sleep")
    def test_missing_cid_still_counts_as_malformed(self, sleep):
        self.client.session.get.return_value = self.response({"PropertyTable": {"Properties": [
            {"SMILES": "C", "IUPACName": "methane"}]}})
        with self.assertRaises(PubChemError):
            self.client.resolve("C")

    @patch("database.services.pubchem.time.sleep")
    def test_permanent_http_error_includes_reason_without_retrying(self, sleep):
        self.client.session.get.return_value = self.response({
            "Fault": {"Message": "Unable to standardize the given structure"},
        }, status=400)
        with self.assertRaisesRegex(PubChemError, "HTTP 400.*Unable to standardize"):
            self.client.resolve("C")
        self.assertEqual(self.client.session.get.call_count, 1)

    @patch("database.services.pubchem.time.sleep")
    def test_exhausted_service_error_reports_http_status(self, sleep):
        response = self.response({}, status=503)
        response.json.side_effect = ValueError("HTML error page")
        self.client.session.get.return_value = response
        with self.assertRaisesRegex(PubChemError, "HTTP 503.*after 3 attempt"):
            self.client.resolve("C")
        self.assertEqual(self.client.session.get.call_count, 3)


class EnrichSpeciesNamesTests(TestCase):
    def setUp(self):
        formula = Formula.objects.create(formula="CH4")
        isomer = Isomer.objects.create(formula=formula, inchi="InChI=1S/CH4/h1H4")
        self.structure = Structure.objects.create(
            isomer=isomer, smiles="C", adjacency_list="methane fixture", multiplicity=1,
        )
        self.result = {"cid": 297, "iupac_name": "methane", "synonyms": ["methane", "marsh gas"]}

    def run_command(self, **options):
        self.output = io.StringIO()
        self.errors = io.StringIO()
        call_command("enrich_species_names", stdout=self.output, stderr=self.errors, **options)

    def another_structure(self, smiles):
        return Structure.objects.create(
            isomer=self.structure.isomer, smiles=smiles,
            adjacency_list=f"fixture {smiles}", multiplicity=1,
        )

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_saves_names_and_skips_completed_structures(self, resolve):
        resolve.return_value = self.result
        self.run_command()
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.iupac_name, "methane")
        self.assertEqual(self.structure.pubchem_cid, 297)
        self.assertIsNotNone(self.structure.names_checked_at)
        self.assertEqual(set(self.structure.names.values_list("name", flat=True)), {"methane", "marsh gas"})
        self.run_command()
        self.assertEqual(resolve.call_count, 1)

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_dry_run_does_not_write(self, resolve):
        resolve.return_value = self.result
        self.run_command(dry_run=True)
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.iupac_name, "")
        self.assertIsNone(self.structure.names_checked_at)
        self.assertFalse(self.structure.names.exists())

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_index_only_never_calls_api(self, resolve):
        Structure.objects.filter(pk=self.structure.pk).update(canonical_smiles="")
        self.run_command(index_only=True)
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.canonical_smiles, "C")
        self.assertIsNone(self.structure.names_checked_at)
        resolve.assert_not_called()

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_no_name_available_is_marked_checked_and_not_retried_by_default(self, resolve):
        resolve.return_value = None
        self.run_command()
        self.structure.refresh_from_db()
        self.assertIsNotNone(self.structure.names_checked_at)
        self.assertEqual(self.structure.iupac_name, "")
        self.assertFalse(self.structure.names.exists())
        self.assertIn("failed 0", self.output.getvalue())
        self.run_command()
        resolve.assert_called_once()

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_verified_cid_is_saved_even_without_names(self, resolve):
        resolve.return_value = {"cid": 297, "iupac_name": "", "synonyms": []}
        self.run_command()
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.pubchem_cid, 297)
        self.assertEqual(self.structure.iupac_name, "")
        self.assertIsNotNone(self.structure.names_checked_at)
        self.assertIn("named 0", self.output.getvalue())
        self.assertIn("PubChem CID 297 (no name available)", self.output.getvalue())

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_api_failure_leaves_record_retryable(self, resolve):
        resolve.side_effect = PubChemError("temporary failure")
        with self.assertRaises(CommandError):
            self.run_command()
        self.structure.refresh_from_db()
        self.assertIsNone(self.structure.names_checked_at)

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_continues_after_isolated_failure_and_resume_only_retries_failed_row(self, resolve):
        later = self.another_structure("CC")
        resolve.side_effect = [PubChemError("HTTP 503"), self.result]
        with self.assertRaisesRegex(CommandError, "Finished with 1 failed"):
            self.run_command()
        later.refresh_from_db()
        self.structure.refresh_from_db()
        self.assertIsNotNone(later.names_checked_at)
        self.assertIsNone(self.structure.names_checked_at)
        self.assertIn(f"Structure {self.structure.pk}: HTTP 503", self.errors.getvalue())
        self.assertIn("failed 1", self.output.getvalue())
        resolve.reset_mock(side_effect=True)
        resolve.return_value = self.result
        self.run_command()
        resolve.assert_called_once_with("C")

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_stops_after_consecutive_failures_without_trying_remaining_rows(self, resolve):
        self.another_structure("CC")
        self.another_structure("CCC")
        resolve.side_effect = PubChemError("HTTP 503")
        with self.assertRaisesRegex(CommandError, "after 2 consecutive failures"):
            self.run_command(max_consecutive_errors=2)
        self.assertEqual(resolve.call_count, 2)
        self.assertFalse(Structure.objects.filter(names_checked_at__isnull=False).exists())

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_success_resets_consecutive_failure_count(self, resolve):
        self.another_structure("CC")
        self.another_structure("CCC")
        resolve.side_effect = [PubChemError("HTTP 503"), None, PubChemError("Timeout")]
        with self.assertRaisesRegex(CommandError, "Finished with 2 failed"):
            self.run_command(max_consecutive_errors=2)
        self.assertEqual(resolve.call_count, 3)

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_failed_refresh_preserves_existing_names(self, resolve):
        self.structure.iupac_name = "methane"
        self.structure.names_checked_at = timezone.now()
        self.structure.save(update_fields=["iupac_name", "names_checked_at"])
        StructureName.objects.create(structure=self.structure, name="marsh gas")
        resolve.side_effect = PubChemError("Timeout")
        with self.assertRaises(CommandError):
            self.run_command(refresh=True)
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.iupac_name, "methane")
        self.assertTrue(self.structure.names.filter(name="marsh gas").exists())

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_invalid_error_threshold_does_not_start_lookups(self, resolve):
        with self.assertRaisesRegex(CommandError, "must be a positive integer"):
            self.run_command(max_consecutive_errors=0)
        resolve.assert_not_called()

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_refresh_replaces_stale_synonyms(self, resolve):
        StructureName.objects.create(structure=self.structure, name="old name")
        Structure.objects.filter(pk=self.structure.pk).update(names_checked_at=timezone.now())
        resolve.return_value = self.result
        self.run_command(refresh=True)
        self.assertFalse(self.structure.names.filter(name="old name").exists())
        self.assertEqual(self.structure.names.count(), 2)

    @patch("database.management.commands.enrich_species_names.PubChemClient.resolve")
    def test_editing_structure_invalidates_old_names(self, resolve):
        resolve.return_value = self.result
        self.run_command()
        self.structure.refresh_from_db()
        self.structure.smiles = "CCO"
        self.structure.save(update_fields=["smiles"])
        self.structure.refresh_from_db()
        self.assertEqual(self.structure.canonical_smiles, "CCO")
        self.assertEqual(self.structure.iupac_name, "")
        self.assertIsNone(self.structure.names_checked_at)
        self.assertFalse(self.structure.names.exists())
