from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rmgpy.molecule import Molecule

from database.models import Structure, ThermoEnrichmentJob as Job, ThermoProviderStatus, ThermoRecord
from database.services import thermo_enrichment as enrichment
from database.services import thermo_sources as sources
from database.tests.test_thermo_sources_unit import METHANE, nasa_fixture

# ATcT writes NO2 with a SMILES RDKit rejects; its InChI is the usable structure.
NO2 = dict(METHANE, ATcT_ID="10102-44-0*0", Name="Nitrogen dioxide", Formula="ONO  (g)", **{
    "∆fH_0K": "36.886", "∆fH_298K": "34.079", "∆fH_298K_uncertainty": "0.066"},
    SMILES="O=[N]=O", CASRN="10102-44-0", InChI="InChI=1S/NO2/c2-1-3")
BENZYL = dict(METHANE, ATcT_ID="2154-56-5*0", Name="Benzyl", Formula="C6H5CH2  (g)", **{
    "∆fH_0K": "230.15", "∆fH_298K": "211.34", "∆fH_298K_uncertainty": "0.51"},
    SMILES="c1ccc(cc1)[CH2]", CASRN="2154-56-5", InChI="InChI=1S/C7H7/c1-7-5-3-2-4-6-7/h2-6H,1H2")


def snapshot_context(items):
    snapshot = tempfile.NamedTemporaryFile(mode="w+", suffix=".json")
    json.dump({"items": items, "total": len(items)}, snapshot)
    snapshot.flush()
    return snapshot, enrichment.EnrichmentContext(atct_snapshot=snapshot.name)


@override_settings(THERMO_ATCT_SNAPSHOT_PATH="")
class ThermoEnrichmentTests(TestCase):
    def setUp(self):
        self.species, self.structure = sources._species_and_structure(Molecule().from_smiles("C"), "Methane")

    def test_signal_and_polling_are_idempotent(self):
        self.assertEqual(Job.objects.count(), 3)
        enrichment.enqueue_missing()
        enrichment.enqueue_missing()
        self.assertEqual(Job.objects.count(), 3)
        Job.objects.all().delete()
        enrichment.enqueue_missing()
        self.assertEqual(Job.objects.count(), 3)

    def test_distinct_claims_and_expired_lease_recovery(self):
        first = enrichment.claim_job(enrichment.PROVIDERS)
        second = enrichment.claim_job(enrichment.PROVIDERS)
        self.assertNotEqual(first.pk, second.pk)
        old_token = first.lease_token
        Job.objects.filter(pk=first.pk).update(started_at=timezone.now() - timedelta(hours=1))
        reclaimed = enrichment.claim_job([first.provider])
        self.assertEqual(reclaimed.pk, first.pk)
        self.assertNotEqual(reclaimed.lease_token, old_token)
        self.assertEqual(enrichment.finish_job(first, "complete", "stale result"), 0)
        self.assertEqual(enrichment.finish_job(reclaimed, "no_match", "checked"), 1)

    def test_circuit_breaker_preserves_other_sources_and_retries(self):
        sources._species_and_structure(Molecule().from_smiles("CC"), "Ethane")
        context = Mock()
        context.atct.side_effect = sources.ATcTRequestError("ATcT HTTP 403", 403)
        context.burcat.return_value = ("no_match", "No exact match", None, "test")
        context.groups.return_value = ("unsupported", "Not supported", None, "test")
        counts = enrichment.process_jobs(context=context)
        self.assertEqual(context.atct.call_count, 1)
        self.assertEqual(Job.objects.filter(provider="atct", status="blocked").count(), 2)
        self.assertEqual(Job.objects.filter(provider="burcat", status="no_match").count(), 2)
        self.assertGreater(ThermoProviderStatus.objects.get(provider="atct").retry_after, timezone.now())
        self.assertEqual(counts["blocked"], 1)
        self.assertIsNone(enrichment.claim_job(["atct"]))
        enrichment.reset_jobs(["atct"])
        self.assertIsNotNone(enrichment.claim_job(["atct"]))

    def test_failed_write_rolls_back_and_schedules_retry(self):
        def failing(structure):
            sources.import_atct(METHANE, multiplicity=1, electronic_state="ground state")
            raise RuntimeError("temporary failure")
        context = Mock()
        context.atct.side_effect = failing
        counts = enrichment.process_jobs(context=context, providers=["atct"], limit=1)
        self.assertEqual(counts, {"failed": 1})
        self.assertFalse(ThermoRecord.objects.exists())
        job = Job.objects.get(provider="atct")
        self.assertGreater(job.next_attempt_at, timezone.now())
        self.assertIsNone(job.lease_token)

    def test_completed_jobs_not_repeated_without_refresh(self):
        context = Mock()
        context.burcat.return_value = ("no_match", "Checked subset", None, "hash")
        enrichment.process_jobs(context=context, providers=["burcat"])
        enrichment.process_jobs(context=context, providers=["burcat"])
        self.assertEqual(context.burcat.call_count, 1)
        enrichment.reset_jobs(["burcat"], refresh=True)
        enrichment.process_jobs(context=context, providers=["burcat"])
        self.assertEqual(context.burcat.call_count, 2)

    def test_monthly_recheck_bypasses_existing_reference_cache(self):
        job = Job.objects.get(provider="atct")
        job.status = "complete"
        job.next_attempt_at = timezone.now() - timedelta(seconds=1)
        job.save()
        context = Mock(refresh=False)
        def check(structure):
            self.assertTrue(context.refresh)
            return "no_match", "checked", None, "version"
        context.atct.side_effect = check
        enrichment.process_jobs(context=context, providers=["atct"])
        self.assertFalse(context.refresh)

    def test_source_configuration_failure_is_blocked(self):
        context = enrichment.EnrichmentContext(database_path="/missing/rmg-database")
        result = enrichment.process_jobs(context=context, providers=["burcat"])
        self.assertEqual(result, {"blocked": 1})

    def test_monitor_api_and_command_status(self):
        Job.objects.filter(provider="atct").update(status="blocked", message="ATcT HTTP 403")
        # Lookup status is for operators; species pages show only source records.
        self.assertNotContains(self.client.get(reverse("species-detail", args=[self.species.pk])), "ATcT HTTP 403")
        response = self.client.get(reverse("api-thermo-enrichment-list"), {"status": "blocked"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertNotIn("lease_token", response.json()["results"][0])
        out = io.StringIO()
        call_command("enrich_species_thermo", status=True, stdout=out)
        self.assertIn('"blocked"', out.getvalue())

    def test_celery_discovers_and_reports_bounded_batch(self):
        from database.tasks import enrich_species_thermo
        with patch.object(enrichment, "process_jobs", return_value={"complete": 2}) as process:
            result = enrich_species_thermo.run(limit=2)
        self.assertEqual(process.call_args.kwargs["limit"], 2)
        self.assertEqual(result["structures_scanned"], 1)
        self.assertEqual(result["attempted"], {"complete": 2})

    def test_dedicated_monitor_schedules_only_thermochemistry(self):
        from kms.celery import app
        def inspect_schedule():
            self.assertEqual(set(app.conf.beat_schedule), {"enrich-species-thermo", "sync-atct-thermo"})
        with tempfile.TemporaryDirectory() as directory, patch.object(app, "Beat") as beat:
            beat.return_value.run.side_effect = inspect_schedule
            call_command("monitor_species_thermo", schedule=str(Path(directory) / "schedule"),
                         pidfile=str(Path(directory) / "pid"), stdout=io.StringIO())

    @patch.object(sources, "find_atct_by_smiles")
    def test_automatic_match_excludes_excited_and_charged_candidates(self, search):
        search.return_value = [METHANE, dict(METHANE, ATcT_ID="excited", Formula="CH4 (g, triplet)"),
                               dict(METHANE, ATcT_ID="cation", SMILES="[CH4+]", InChI="InChI=1S/CH4/h1H4/q+1", charge=1)]
        result = enrichment.EnrichmentContext().atct(self.structure)
        self.assertEqual(result[0], "complete")
        record = result[2]
        self.assertEqual(record.external_id, "74-82-8*0")
        self.assertIn("Automatic match", record.provenance)
        self.assertEqual(record.enthalpy_298, -74513)

    @patch.object(sources, "find_atct_by_smiles")
    def test_atct_match_derives_constrained_thermo(self, search):
        search.return_value = [METHANE]
        sources.save_record(self.structure.to_rmg(), provider="group_additivity", external_id="methane-estimate",
                            source_version="v1", label="methane", nasa=nasa_fixture(), enthalpy_298=-73000)
        enrichment.EnrichmentContext().atct(self.structure)
        derived = ThermoRecord.objects.get(provider="atct_constrained")
        self.assertAlmostEqual(derived.nasa_thermo.enthalpy298, -74513, delta=1)
        # The derived provider has no lookup jobs of its own.
        self.assertFalse(Job.objects.filter(provider="atct_constrained").exists())

    @patch.object(sources, "find_atct_by_smiles")
    def test_ambiguous_candidates_are_not_imported(self, search):
        search.return_value = [METHANE, dict(METHANE, ATcT_ID="different")]
        result = enrichment.EnrichmentContext().atct(self.structure)
        self.assertEqual(result[0], "review")
        self.assertFalse(ThermoRecord.objects.exists())

    def test_unparseable_atct_smiles_matches_by_inchi(self):
        _, no2 = sources._species_and_structure(Molecule().from_smiles("[O]N=O"), "NO2")
        snapshot, context = snapshot_context([METHANE, NO2])
        with snapshot:
            status, message, record, _ = context.atct(no2)
        self.assertEqual(status, "complete")
        self.assertEqual(record.structure, no2)
        self.assertEqual(record.enthalpy_298, 34079)
        self.assertIn("ATcT InChI", record.provenance)

    def test_resonance_form_links_record_without_new_structures(self):
        _, separated = sources._species_and_structure(Molecule().from_smiles("[O-][N+]=O"), "NO2 (separated)")
        structures = Structure.objects.count()
        snapshot, context = snapshot_context([METHANE, NO2])
        with snapshot:
            status, message, record, _ = context.atct(separated)
            self.assertEqual(status, "complete")
            self.assertIn("resonance structure", message)
            self.assertEqual((record.structure, Structure.objects.count()), (separated, structures))
            # A structure drawn as ATcT draws it, under another isomer, reuses the record.
            species, drawn = sources._species_and_structure(Molecule().from_smiles("[O]N=O"), "NO2")
            self.assertNotEqual(drawn.isomer, separated.isomer)
            self.assertEqual(context.atct(drawn)[:3], ("complete", f"Matched the ATcT record on equivalent structure {separated.pk}.", record))
            # Rechecking keeps the record where it is now that the drawn structure exists.
            self.assertEqual(context.atct(separated)[2].structure, separated)
        Job.objects.filter(structure=drawn, provider="atct").update(status="complete", record=record)
        self.assertContains(self.client.get(reverse("species-detail", args=[species.pk])), "10102-44-0*0")

    @patch.object(sources, "find_atct_by_smiles")
    def test_quinoid_drawing_matches_aromatic_record(self, search):
        search.side_effect = lambda smiles, session=None: [BENZYL] if smiles == "[CH2]c1ccccc1" else []
        _, quinoid = sources._species_and_structure(Molecule().from_smiles("C=C1[CH]C=CC=C1"), "Benzyl (quinoid)")
        status, message, record, _ = enrichment.EnrichmentContext().atct(quinoid)
        self.assertEqual((status, record.structure), ("complete", quinoid))
        self.assertIn("resonance-equivalent graph", record.provenance)

    @patch.object(sources, "atct_request")
    def test_search_pagination_and_incomplete_response(self, request):
        request.side_effect = [{"items": [METHANE], "total": 2}, {"items": [], "total": 2}]
        with self.assertRaisesRegex(sources.ATcTRequestError, "pagination"):
            sources.find_atct_by_smiles("C")
        request.side_effect = [{"items": [METHANE], "total": 2}, {"items": [dict(METHANE, ATcT_ID="second")], "total": 2}]
        self.assertEqual(len(sources.find_atct_by_smiles("C")), 2)


class ATcTCatalogTests(SimpleTestCase):
    @patch.object(sources, "atct_request")
    def test_catalog_atomicity_and_coverage(self, request):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "catalog.json"
            request.side_effect = [{"items": [METHANE], "total": 2},
                                   {"items": [dict(METHANE, ATcT_ID="second")], "total": 2}]
            result = sources.sync_atct_catalog(destination)
            self.assertEqual(result["records"], 2)
            saved = destination.read_text()
            request.side_effect = [{"items": [METHANE], "total": 2}, {"items": [], "total": 2}]
            with self.assertRaises(sources.ATcTRequestError):
                sources.sync_atct_catalog(destination)
            self.assertEqual(destination.read_text(), saved)
            request.side_effect = [{"items": [METHANE, METHANE], "total": 2}]
            with self.assertRaises(sources.ATcTRequestError):
                sources.sync_atct_catalog(destination)
            self.assertEqual(destination.read_text(), saved)

    def test_preferred_formulas_compare_by_composition(self):
        for a, b in [("NH3", "H3N"), ("HCOOH", "CH2O2"), ("(CH3)2CO", "C3H6O"), ("[NH4]+", "H4N+")]:
            with self.subTest(formulas=(a, b)):
                self.assertEqual(sources.formula_composition(a), sources.formula_composition(b))
        self.assertNotEqual(sources.formula_composition("CO"), sources.formula_composition("CO2"))

    def test_inchi_structure_requires_faithful_round_trip(self):
        self.assertEqual(sources.atct_structure_smiles(NO2), "[O]N=O")
        # RDKit drops this cation's charge layer; it must not index as neutral ethane.
        cation = dict(METHANE, SMILES="C[CH3+]", InChI="InChI=1S/C2H6/c1-2/h1-2H3/q+1", charge=1)
        self.assertIsNone(sources.atct_structure_smiles(cation))

    def test_partial_snapshot_is_rejected(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as snapshot:
            json.dump({"items": [METHANE], "total": 2}, snapshot)
            snapshot.flush()
            context = enrichment.EnrichmentContext(atct_snapshot=snapshot.name)
            with self.assertRaisesRegex(sources.ATcTRequestError, "incomplete"):
                context.atct_candidates("C")
