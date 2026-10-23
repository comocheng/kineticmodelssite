from celery import shared_task
from django.conf import settings
from pathlib import Path


@shared_task(bind=True, name="database.enrich_species_thermo", soft_time_limit=840, time_limit=900)
def enrich_species_thermo(self, limit=None):
    """Beat discovers new species, then processes a bounded, recoverable batch."""
    from database.services.thermo_enrichment import enqueue_missing, process_jobs, status_summary
    if settings.THERMO_ATCT_SNAPSHOT_PATH and not Path(settings.THERMO_ATCT_SNAPSHOT_PATH).exists():
        # Bootstrap catalog access; an unavailable provider must not prevent GA/Burcat work.
        try:
            sync_atct_catalog.run()
        except Exception:
            pass  # The durable source jobs will expose the missing catalog/access failure.
    structures = enqueue_missing()
    def progress(job, status, message, counts):
        self.update_state(state="PROGRESS", meta={"attempted": sum(counts.values()), "counts": counts,
                                                 "structure_id": job.structure_id, "provider": job.provider,
                                                 "status": status})
    counts = process_jobs(limit=limit or settings.THERMO_ENRICHMENT_BATCH_SIZE, progress=progress)
    return {"structures_scanned": structures, "attempted": counts, "queue": status_summary()}


@shared_task(name="database.sync_atct_catalog", soft_time_limit=840, time_limit=900)
def sync_atct_catalog():
    from database.services.thermo_sources import sync_atct_catalog as download
    from database.services.thermo_enrichment import reset_jobs
    if not settings.THERMO_ATCT_SNAPSHOT_PATH:
        return {"status": "live-lookups-configured"}
    result = download(settings.THERMO_ATCT_SNAPSHOT_PATH)
    if result["changed"]:
        reset_jobs(["atct"], refresh=True)
    return result
