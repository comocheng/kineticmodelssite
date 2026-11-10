"""Durable, leased work shared by the CLI and Celery. Matching never uses formula alone."""

from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import timedelta
import json
import logging
from pathlib import Path
import signal
import threading
import uuid
import requests

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from database.models import Structure, ThermoEnrichmentJob as Job, ThermoProviderStatus, ThermoRecord
from database.services import thermo_sources as sources
from database.services.chemical_identity import canonical_smiles

logger = logging.getLogger(__name__)
PROVIDERS = ThermoRecord.SOURCE_PROVIDERS
LEASE_TIME = timedelta(minutes=30)


class JobTimeoutError(Exception):
    pass


@contextmanager
def job_timeout():
    seconds = getattr(settings, "THERMO_JOB_TIMEOUT_SECONDS", 120)
    enabled = seconds > 0 and threading.current_thread() is threading.main_thread() and hasattr(signal, "setitimer")
    if not enabled:
        yield
        return
    def expired(signum, frame):
        raise JobTimeoutError(f"Structure processing exceeded {seconds} seconds; retry scheduled.")
    previous = signal.signal(signal.SIGALRM, expired)
    timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *timer)
        signal.signal(signal.SIGALRM, previous)


def enqueue_missing(providers=PROVIDERS, structure_ids=None):
    """Polling also catches bulk_create and imported species that bypass signals."""
    structures = Structure.objects.filter(isomer__species__isnull=False).distinct()
    if structure_ids is not None:
        structures = structures.filter(pk__in=structure_ids)
    ids = list(structures.values_list("pk", flat=True))
    for start in range(0, len(ids), 500):
        Job.objects.bulk_create([Job(structure_id=pk, provider=provider)
                                 for pk in ids[start:start + 500] for provider in providers], ignore_conflicts=True)
    for state in ThermoProviderStatus.objects.filter(retry_after__gt=timezone.now(), provider__in=providers):
        Job.objects.filter(provider=state.provider, status=Job.Status.PENDING).update(
            status=Job.Status.BLOCKED, message=state.message, next_attempt_at=state.retry_after, updated_at=timezone.now())
    return len(ids)


def reset_jobs(providers=PROVIDERS, *, refresh=False):
    jobs = Job.objects.filter(provider__in=providers).exclude(status=Job.Status.RUNNING)
    if not refresh:
        jobs = jobs.filter(status__in=[Job.Status.FAILED, Job.Status.BLOCKED, Job.Status.REVIEW, Job.Status.UNSUPPORTED])
    count = jobs.update(status=Job.Status.PENDING, next_attempt_at=None, message="", finished_at=None,
                        source_version="", updated_at=timezone.now())
    ThermoProviderStatus.objects.filter(provider__in=providers).update(retry_after=None, message="")
    return count


def status_summary():
    return list(Job.objects.values("provider", "status").annotate(count=Count("id")).order_by("provider", "status"))


def claim_job(providers):
    now = timezone.now()
    blocked = ThermoProviderStatus.objects.filter(retry_after__gt=now).values_list("provider", flat=True)
    eligible = Q(status=Job.Status.PENDING) | Q(
        status__in=[Job.Status.FAILED, Job.Status.BLOCKED, Job.Status.COMPLETE, Job.Status.NO_MATCH], next_attempt_at__lte=now
    ) | Q(status=Job.Status.RUNNING, started_at__lt=now - LEASE_TIME)
    with transaction.atomic():
        job = (Job.objects.select_for_update(skip_locked=True).filter(eligible, provider__in=providers)
               .exclude(provider__in=blocked).order_by("structure_id", "provider").first())
        if job is None:
            return None
        job.refresh_due = job.status in (Job.Status.COMPLETE, Job.Status.NO_MATCH)
        job.status = Job.Status.RUNNING
        job.attempts += 1
        job.started_at = now
        job.lease_token = uuid.uuid4()
        job.save(update_fields=["status", "attempts", "started_at", "lease_token", "updated_at"])
    return job


def finish_job(job, status, message, record=None, version=""):
    next_attempt = None
    if status == Job.Status.FAILED:
        next_attempt = timezone.now() + timedelta(minutes=min(1440, 5 * 2 ** min(job.attempts, 8)))
    if status in (Job.Status.NO_MATCH, Job.Status.COMPLETE):
        next_attempt = timezone.now() + timedelta(days=30)
    return Job.objects.filter(pk=job.pk, lease_token=job.lease_token).update(
        status=status, message=message[:4000], record=record, source_version=version,
        next_attempt_at=next_attempt, finished_at=timezone.now(), lease_token=None, updated_at=timezone.now())


def block_provider(job, message, hours=1):
    retry = timezone.now() + timedelta(hours=hours)
    ThermoProviderStatus.objects.update_or_create(provider=job.provider, defaults={"retry_after": retry, "message": message[:4000]})
    # Mark the queue truthfully without thousands of identical failed HTTP requests.
    Job.objects.filter(provider=job.provider).filter(
        Q(status__in=[Job.Status.PENDING, Job.Status.FAILED, Job.Status.BLOCKED]) |
        Q(pk=job.pk, lease_token=job.lease_token)
    ).update(status=Job.Status.BLOCKED, message=message[:4000], next_attempt_at=retry,
             finished_at=timezone.now(), lease_token=None, updated_at=timezone.now())


class EnrichmentContext:
    def __init__(self, database_path=None, atct_snapshot=None, refresh=False):
        self.database_path = database_path or getattr(settings, "THERMO_RMG_DATABASE_PATH", None)
        self.snapshot_path = atct_snapshot or getattr(settings, "THERMO_ATCT_SNAPSHOT_PATH", "")
        self.refresh = refresh
        self._groups = None
        self._burcat = None
        self._snapshot = None
        self._atct_cache = {}
        self._http_session = requests.Session()

    def constrain(self, atct_records):
        """Keep ATcT-constrained thermo current. A failure here never fails the source lookup."""
        for record in atct_records:
            try:
                sources.derive_atct_constrained(record)
            except sources.ThermoSourceError as exc:
                logger.warning("ATcT-constrained thermo for record %s not derived: %s", record.pk, exc)

    def constrain_structure(self, structure):
        self.constrain(ThermoRecord.objects.filter(provider="atct", structure__isomer=structure.isomer,
                                                   structure__multiplicity=structure.multiplicity))

    def existing(self, structure, provider, version=None):
        records = ThermoRecord.objects.filter(structure__isomer=structure.isomer, provider=provider)
        if version:
            records = records.filter(source_version=version)
        return records.order_by("-retrieved_at").first()

    def burcat(self, structure):
        if self._burcat is None:
            try:
                root = sources.rmg_database_path(self.database_path)
                library_path = getattr(settings, "THERMO_BURCAT_LIBRARY", "") or root / "input/thermo/libraries/BurcatNS.py"
                library, version = sources.load_burcat(library_path)
            except Exception as exc:
                raise OSError("Burcat library could not be loaded") from exc
            index = defaultdict(list)
            for entry in library.entries.values():
                index[entry.item.get_formula()].append(entry)
            self._burcat = library, version, index
        library, version, index = self._burcat
        existing = self.existing(structure, "burcat", version)
        if existing and not self.refresh:
            return Job.Status.COMPLETE, "Matched imported Burcat record.", existing, version
        molecule = structure.to_rmg()
        entries = [entry for entry in index[molecule.get_formula()] if entry.item.is_isomorphic(molecule)]
        if not entries:
            return Job.Status.NO_MATCH, f"No exact structure/spin match in {library.name} (curated subset).", None, version
        records = [sources.import_burcat_entry(library, version, entry) for entry in entries]
        self.constrain_structure(structure)
        return Job.Status.COMPLETE, f"Matched {len(records)} {library.name} record(s).", records[0], version

    def groups(self, structure):
        import rmgpy
        if self._groups is None:
            try:
                self._groups = sources.load_groups(self.database_path)
            except Exception as exc:
                raise OSError("RMG groups could not be loaded") from exc
        database, digest = self._groups
        version = f"rmg-{rmgpy.__version__}:{digest}"
        existing = self.existing(structure, "group_additivity", version)
        if existing and not self.refresh:
            return Job.Status.COMPLETE, "Matched existing estimate for this group-data version.", existing, version
        record = sources.estimate_groups(structure, database, digest)
        self.constrain_structure(structure)
        return Job.Status.COMPLETE, "Group-additivity estimate and NASA fit validated.", record, version

    def atct_candidates(self, smiles):
        if self.snapshot_path:
            if self._snapshot is None:
                data = json.loads(Path(self.snapshot_path).read_text())
                items = data if isinstance(data, list) else data.get("items") if isinstance(data, dict) else None
                if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                    raise sources.ATcTRequestError("ATcT snapshot must be a list of API record objects or an items collection.")
                if isinstance(data, dict) and int(data.get("total", len(items))) != len(items):
                    raise sources.ATcTRequestError("ATcT snapshot is incomplete; export all pages before importing.")
                self._snapshot = defaultdict(list)
                for item in items:
                    key = canonical_smiles(sources.atct_structure_smiles(item))
                    if key:
                        self._snapshot[key].append(item)
            return self._snapshot.get(smiles, [])
        if smiles not in self._atct_cache:
            self._atct_cache[smiles] = sources.find_atct_by_smiles(smiles, session=self._http_session)
        return self._atct_cache[smiles]

    def atct(self, structure):
        existing = self.existing(structure, "atct")
        if existing and not self.refresh and not self.snapshot_path:
            return Job.Status.COMPLETE, "Matched previously imported ATcT reference; version shown on record.", existing, existing.source_version
        if "molecularTermSymbol" in structure.adjacency_list:
            return Job.Status.REVIEW, "Explicit electronic term symbol requires a reviewed ATcT state mapping.", None, ""
        molecule = structure.to_rmg()
        if molecule.get_radical_count() > 1:
            return Job.Status.REVIEW, "Multiple unpaired electrons: automatic ATcT spin/state assignment is not safe.", None, ""
        smiles = canonical_smiles(molecule.to_smiles())
        if not smiles:
            return Job.Status.REVIEW, "No usable canonical structure for ATcT matching.", None, ""
        forms = sources.resonance_forms(molecule)
        keys = {smiles}
        candidates = self.atct_candidates(smiles)
        if not candidates:
            # ATcT may draw the species as another resonance structure (benzyl, vinoxy, N2O).
            keys = {key for key in (canonical_smiles(form.to_smiles()) for form in forms) if key}
            candidates = [item for key in sorted(keys - {smiles}) for item in self.atct_candidates(key)]
        if not candidates:
            scope = "configured ATcT snapshot" if self.snapshot_path else "ATcT API search"
            return Job.Status.NO_MATCH, f"No candidates in {scope} for this structure or its resonance forms.", None, ""
        matches, rejected = [], []
        for item in candidates:
            if canonical_smiles(sources.atct_structure_smiles(item)) not in keys:
                continue
            # Only the unqualified gas record is automatic. Explicit excited states,
            # conformers, isotope labels and ambiguous state descriptors need review.
            import re
            if not re.fullmatch(r"\s*\S+\s+\(g\)\s*", str(item.get("Formula", ""))):
                rejected.append("phase/state descriptor")
                continue
            if re.search(r"excited|singlet|triplet|doublet|quartet|quintet", str(item.get("Name", "")), re.I):
                rejected.append("electronic state in name")
                continue
            matches.append(item)
        identities = {(item.get("ATcT_ID"), item.get("ATcT_TN_Version")) for item in matches}
        if len(identities) != 1:
            return Job.Status.REVIEW, "ATcT candidates do not identify one unqualified gas-phase structure/state; manual review required.", None, ""
        item = matches[0]
        from rmgpy.molecule import Molecule
        atct_molecule = Molecule().from_smiles(sources.atct_structure_smiles(item))
        # Aromatic/Kekulé rings and other resonance drawings are the same species.
        if not sources.resonance_equivalent(atct_molecule, molecule):
            return Job.Status.REVIEW, "ATcT molecular graph or spin differs from the local structure and its resonance forms.", None, ""
        record = ThermoRecord.objects.filter(provider="atct", external_id=item["ATcT_ID"],
                                             source_version=item["ATcT_TN_Version"]).first()
        if record is not None and record.structure_id != structure.pk:
            return Job.Status.COMPLETE, f"Matched the ATcT record on equivalent structure {record.structure_id}.", record, record.source_version
        exact = atct_molecule.is_isomorphic(molecule)
        target = None
        if not exact:
            # Keep an existing record in place. Otherwise link to a structure drawn as ATcT
            # draws it if one exists; a resonance match creates none.
            drawn = [] if record else Structure.objects.filter(
                canonical_smiles=canonical_smiles(atct_molecule.to_smiles()),
                multiplicity=structure.multiplicity, isomer__species__isnull=False).distinct()
            target = next((s for s in drawn if s.to_rmg().is_isomorphic(atct_molecule)), structure)
        graph = "exact graph" if exact else "resonance-equivalent graph"
        record = sources.import_atct(item, multiplicity=structure.multiplicity, structure=target,
                                     electronic_state=f"Unqualified gas-phase record; {graph}, exact charge and multiplicity")
        record.provenance = record.provenance.replace("Electronic state reviewed by importer.",
            f"Automatic match to the unqualified gas-phase record; {graph}, exact charge/multiplicity, at most one unpaired electron.")
        if self.snapshot_path:
            record.provenance += " Imported from configured ATcT JSON snapshot; timestamp is the local import time."
        record.save(update_fields=["provenance"])
        self.constrain([record])
        found = "Exact ATcT structure/state match" if exact else f"ATcT match via resonance structure {atct_molecule.to_smiles()}"
        return Job.Status.COMPLETE, f"{found} imported.", record, record.source_version


def process_jobs(*, providers=PROVIDERS, limit=None, context=None, progress=None):
    context = context or EnrichmentContext()
    counts = Counter()
    while limit is None or sum(counts.values()) < limit:
        job = claim_job(providers)
        if job is None:
            break
        previous_refresh = context.refresh
        try:
            structure = Structure.objects.select_related("isomer").get(pk=job.structure_id)
            method = {"atct": context.atct, "burcat": context.burcat, "group_additivity": context.groups}[job.provider]
            # Keep source writes and completion atomic. A stale worker cannot publish
            # after another worker reclaims its lease.
            context.refresh = previous_refresh or job.refresh_due
            with transaction.atomic(), job_timeout():
                locked = Job.objects.select_for_update().filter(pk=job.pk, lease_token=job.lease_token).first()
                if locked is None:
                    continue
                status, message, record, version = method(structure)
                finish_job(job, status, message, record, version)
        except JobTimeoutError as exc:
            status, message = Job.Status.FAILED, str(exc)
            finish_job(job, status, message)
        except sources.ATcTRequestError as exc:
            message = str(exc)
            block_provider(job, message, hours=24 if exc.status in (401, 403) else 1)
            status = Job.Status.BLOCKED
        except (FileNotFoundError, OSError) as exc:
            message = f"Source configuration unavailable: {type(exc).__name__}. Check database/snapshot paths."
            block_provider(job, message)
            status = Job.Status.BLOCKED
        except Exception as exc:
            from billiard.exceptions import SoftTimeLimitExceeded
            if isinstance(exc, SoftTimeLimitExceeded):
                finish_job(job, Job.Status.FAILED, "Worker time limit reached; retry scheduled.")
                raise
            from rmgpy.exceptions import DatabaseError
            if isinstance(exc, (sources.ThermoSourceError, DatabaseError, ValueError)):
                status = Job.Status.UNSUPPORTED if job.provider == "group_additivity" else Job.Status.REVIEW
            else:
                status = Job.Status.FAILED
            message = f"{type(exc).__name__}: {exc}"
            finish_job(job, status, message)
            logger.debug("Thermo job %s: %s", job.pk, message)
        finally:
            context.refresh = previous_refresh
        counts[status] += 1
        if progress:
            progress(job, status, message, dict(counts))
    return dict(counts)
