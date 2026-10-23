from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from chemked_database.models import CompositionSpecies
from chemked_database.utils.chemistry import rdkit_available


class Command(BaseCommand):
    help = "Backfill SMILES/atomic composition for CompositionSpecies with InChI"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview updates without saving")
        parser.add_argument("--limit", type=int, default=None, help="Limit number of rows")

    def handle(self, *args, **options):
        if not rdkit_available():
            self.stderr.write("RDKit is not available; cannot generate SMILES/atomic composition.")
            return

        queryset = CompositionSpecies.objects.filter(
            inchi__isnull=False
        ).exclude(inchi="").filter(Q(smiles="") | Q(atomic_composition__isnull=True))

        limit = options.get("limit")
        if limit:
            queryset = queryset[:limit]

        updated_smiles = 0
        updated_atomic = 0
        total = 0

        for species in queryset:
            total += 1
            updated = species.populate_identifiers()
            if not updated:
                continue

            if options["dry_run"]:
                if species.smiles:
                    updated_smiles += 1
                if species.atomic_composition:
                    updated_atomic += 1
                continue

            species.save(update_fields=["smiles", "atomic_composition"])
            if species.smiles:
                updated_smiles += 1
            if species.atomic_composition:
                updated_atomic += 1

        mode = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(
            f"{mode} {total} species. SMILES: {updated_smiles}, atomic composition: {updated_atomic}."
        )
