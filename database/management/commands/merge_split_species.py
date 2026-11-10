"""Merge species records that are one species (they share a structure key in one electronic state).

Older imports made one record for a thermo entry's single resonance form and another for the
reaction's full set. The record with the most forms is kept (the one the importer picks); every
row that refers to the others is moved to it, and reactions and kinetics that become identical
are merged. Run before rebuild_model_links.

Usage:
    python manage.py merge_split_species          # dry run: does the work and rolls it back
    python manage.py merge_split_species --apply
"""
from django.core.management.base import BaseCommand

from database.services.cleanup import merge_split_species


class Command(BaseCommand):
    help = "Merge species records that share a structure key in the same electronic state."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")

    def handle(self, *args, **options):
        report = merge_split_species(apply=options["apply"], log=self.stdout.write)
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
