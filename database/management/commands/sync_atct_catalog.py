from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from database.services.thermo_sources import sync_atct_catalog


class Command(BaseCommand):
    help = "Download the complete ATcT API wildcard-search catalog, preserving the last snapshot on failure."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=settings.THERMO_ATCT_SNAPSHOT_PATH)

    def handle(self, *args, **options):
        if not options["output"]:
            raise CommandError("Set THERMO_ATCT_SNAPSHOT_PATH or provide --output.")
        try:
            result = sync_atct_catalog(options["output"])
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Saved {result['records']} ATcT records; versions {', '.join(result['versions'])}; changed: {result['changed']}.")
