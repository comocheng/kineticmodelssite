from django.core.management.base import BaseCommand

from database.services import chemistry_index


class Command(BaseCommand):
    help = ("Fill structure keys, direction-insensitive reaction keys and layers, and rate fingerprints "
            "(the identity shared with RMG-Py's evidence index). Resumes where it stopped.")

    def add_arguments(self, parser):
        parser.add_argument("--refresh", action="store_true", help="Recompute every row, not just missing ones")

    def handle(self, *args, **options):
        refresh = options["refresh"]
        # Reaction keys need structure keys first.
        self.stdout.write(f"Structures keyed: {chemistry_index.index_structures(refresh)}")
        self.stdout.write(f"Reactions indexed: {chemistry_index.index_reactions(refresh)}")
        self.stdout.write(f"Kinetics fingerprinted: {chemistry_index.index_kinetics(refresh)}")
