"""Merge the variant species records of migration 0019 into the record of their structure and state.

0019 gave a model's later name for a structure it already lists (furop2 after furop1) a record of
its own, "<model name>: <label>". One record per species is kept instead: the name stays, as a
second name of the model for the shared record, and so do its thermo links (they name it) and its
kinetics links (they name it where they write it). Run between migration 0021 and 0022:

    python manage.py migrate database 0021
    python manage.py fold_species_variants          # dry run: does the work and rolls it back
    python manage.py fold_species_variants --apply
    python manage.py migrate
"""
from django.core.management.base import BaseCommand

from database.services.cleanup import fold_species_variants


class Command(BaseCommand):
    help = "Merge each variant species record into the shared record of its structure and state."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")

    def handle(self, *args, **options):
        report = fold_species_variants(apply=options["apply"], log=self.stdout.write)
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
