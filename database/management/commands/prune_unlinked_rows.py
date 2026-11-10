"""Delete thermo, kinetics, reaction and species rows that nothing refers to any more.

After merge_split_species and rebuild_model_links, the rows only the old links used are left
over. A row that provider data or a derived table (ChemistryBlock, SemanticMapping, ...) still
refers to is kept and counted; rebuild those tables, then run this again.

Usage:
    python manage.py prune_unlinked_rows          # dry run
    python manage.py prune_unlinked_rows --apply
"""
from django.core.management.base import BaseCommand

from database.services.cleanup import prune_unlinked_rows


class Command(BaseCommand):
    help = "Delete thermo, kinetics, reaction and species rows that nothing refers to."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")

    def handle(self, *args, **options):
        report = prune_unlinked_rows(apply=options["apply"])
        for table, counts in report.items():
            self.stdout.write(f"{table}: {counts}")
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
