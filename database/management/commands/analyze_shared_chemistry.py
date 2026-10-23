from django.core.management.base import BaseCommand

from database.services import shared_chemistry


class Command(BaseCommand):
    help = ("Find which models use the same chemistry: per-layer overlap between every pair of models, "
            "blocks of identical rates copied between models, and each layer's sub-mechanisms and their "
            "variants. Rerun after imports.")

    def handle(self, *args, **options):
        counts = shared_chemistry.analyze()
        self.stdout.write(f"Model pairs x layers: {counts['pairs']}, copied blocks: {counts['blocks']}, "
                          f"distinct rates: {counts['rates']}")
        self.stdout.write(f"Sub-mechanisms: {counts['sub_mechanisms']} ({counts['shared']} used by more than one model), "
                          f"variants: {counts['variants']}")
