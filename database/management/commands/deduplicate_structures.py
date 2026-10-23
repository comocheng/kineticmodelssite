"""Remove duplicate Structure rows that are isomorphic to an earlier row.

Usage:
    python manage.py deduplicate_structures          # dry-run (default)
    python manage.py deduplicate_structures --apply   # actually delete
"""
import logging
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Min

from database.models import Structure

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deduplicate Structure records that differ only in atom numbering."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete duplicates (default is dry-run).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]

        # Group structures by (isomer_id, multiplicity) — candidates for
        # isomorphic duplicates share these fields.
        groups = defaultdict(list)
        for s in Structure.objects.order_by("pk").iterator():
            groups[(s.isomer_id, s.multiplicity)].append(s)

        to_delete = []
        for key, structs in groups.items():
            if len(structs) < 2:
                continue
            # Keep the first (lowest pk) representative of each unique graph.
            kept = []  # list of (Structure, rmg Molecule) pairs
            for s in structs:
                try:
                    mol = s.to_rmg()
                except Exception:
                    # Can't parse → keep it to be safe
                    continue
                is_dup = False
                for kept_s, kept_mol in kept:
                    try:
                        if mol.is_isomorphic(kept_mol):
                            is_dup = True
                            to_delete.append((s, kept_s))
                            break
                    except Exception:
                        continue
                if not is_dup:
                    kept.append((s, mol))

        self.stdout.write(f"Found {len(to_delete)} duplicate structure(s).")

        if not to_delete:
            return

        if not apply:
            for dup, canonical in to_delete[:20]:
                self.stdout.write(
                    f"  Would delete pk={dup.pk} (dup of pk={canonical.pk}): "
                    f"smiles={dup.smiles}"
                )
            if len(to_delete) > 20:
                self.stdout.write(f"  ... and {len(to_delete) - 20} more.")
            self.stdout.write("Re-run with --apply to delete them.")
            return

        ids = [dup.pk for dup, _ in to_delete]
        deleted_count, _ = Structure.objects.filter(pk__in=ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} duplicate structure(s)."))
