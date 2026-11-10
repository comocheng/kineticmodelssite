import json
from django.core.management.base import BaseCommand, CommandError
from database.services.thermo_enrichment import (
    PROVIDERS, EnrichmentContext, enqueue_missing, process_jobs, reset_jobs, status_summary,
)


class Command(BaseCommand):
    help = "Backfill all species thermochemistry, or inspect/enqueue durable work monitored by Celery."

    def add_arguments(self, parser):
        parser.add_argument("--provider", action="append", choices=PROVIDERS)
        parser.add_argument("--limit", type=int, help="Maximum source/structure jobs to attempt (default: all due jobs)")
        parser.add_argument("--database-path")
        parser.add_argument("--atct-snapshot", help="Complete API JSON collection, used instead of live ATcT requests")
        parser.add_argument("--enqueue-only", action="store_true")
        parser.add_argument("--status", action="store_true")
        parser.add_argument("--retry-failed", action="store_true", help="Requeue failed, blocked, unsupported, and review jobs")
        parser.add_argument("--refresh", action="store_true", help="Recheck completed/no-match jobs too")

    def handle(self, *args, **options):
        if options["status"]:
            self.stdout.write(json.dumps(status_summary(), indent=2))
            return
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be positive.")
        providers = options["provider"] or PROVIDERS
        total = enqueue_missing(providers)
        self.stdout.write(f"Checked {total} structures for missing source jobs.")
        if options["retry_failed"] or options["refresh"]:
            reset_jobs(providers, refresh=options["refresh"])
        if options["enqueue_only"]:
            self.stdout.write(json.dumps(status_summary()))
            return
        def progress(job, status, message, counts):
            n = sum(counts.values())
            if n % 50 == 0 or status in ("blocked", "failed") or options["verbosity"] > 1:
                self.stdout.write(f"{n} attempted; structure {job.structure_id} / {job.provider}: {status}. {message}")
                self.stdout.flush()
        counts = process_jobs(providers=providers, limit=options["limit"], progress=progress,
                              context=EnrichmentContext(options["database_path"], options["atct_snapshot"], options["refresh"]))
        self.stdout.write(f"This run: {json.dumps(counts)}")
        self.stdout.write(f"Queue: {json.dumps(status_summary())}")
        if counts.get("failed") or counts.get("blocked"):
            raise CommandError("Some source jobs failed or are blocked. Progress is saved; inspect --status and retry after resolving the cause.")
