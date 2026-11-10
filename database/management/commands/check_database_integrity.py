"""Count the identity defects that older imports left (split species records, wrong and
duplicate links, stale hashes, rows nothing refers to). Reads only; run it before and after
the clean-up as the evidence.

Usage:
    python manage.py check_database_integrity
    python manage.py check_database_integrity --json report.json
"""
import json

from django.core.management.base import BaseCommand

from database.services.cleanup import integrity_report


class Command(BaseCommand):
    help = "Report the identity defects that merge_split_species, rebuild_model_links and prune_unlinked_rows repair."

    def add_arguments(self, parser):
        parser.add_argument("--json", help="Also write the report to this file.")

    def handle(self, *args, **options):
        report = integrity_report()
        width = max(len(k) for k in report)
        for key, value in report.items():
            if key != "examples":
                self.stdout.write(f"{key:<{width}}  {value}")
        for key, value in report["examples"].items():
            self.stdout.write(f"example {key}: {value}")
        if options["json"]:
            with open(options["json"], "w") as handle:
                json.dump(report, handle, indent=2, default=list)
