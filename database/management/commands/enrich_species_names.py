from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from database.models import Structure, StructureName
from database.services.chemical_identity import canonical_smiles
from database.services.pubchem import PubChemClient, PubChemError


class Command(BaseCommand):
    help = "Index exact structures and cache PubChem IUPAC names/synonyms for species search."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int)
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true", help="Resolve without saving changes")
        parser.add_argument("--refresh", action="store_true", help="Recheck resolved rows")
        parser.add_argument("--index-only", action="store_true", help="Index without API requests")
        parser.add_argument(
            "--max-consecutive-errors", type=int, default=5,
            help="Stop after this many consecutive API failures (default: 5; use 1 to fail fast)",
        )

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer")
        if options["max_consecutive_errors"] < 1:
            raise CommandError("--max-consecutive-errors must be a positive integer")
        queryset = Structure.objects.filter(pk__gt=options["after_id"]).order_by("pk")
        if not options["refresh"]:
            if options["index_only"]:
                queryset = queryset.filter(canonical_smiles="")
            else:
                queryset = queryset.filter(names_checked_at__isnull=True)
        if options["limit"]:
            queryset = queryset[:options["limit"]]

        client = PubChemClient()
        resolve = lru_cache(maxsize=256)(client.resolve)
        indexed = named = skipped = failed = consecutive_errors = 0
        stopped_at = None
        for structure in queryset.iterator(chunk_size=100):
            identity = canonical_smiles(structure.smiles)
            if not identity:
                try:
                    identity = canonical_smiles(structure.to_rmg().to_smiles())
                except Exception as exc:
                    self.stderr.write(f"Structure {structure.pk}: cannot read structure ({exc})")
            if not identity:
                skipped += 1
                continue
            result = None
            if not options["index_only"]:
                try:
                    result = resolve(identity)
                except PubChemError as exc:
                    failed += 1
                    consecutive_errors += 1
                    self.stderr.write(
                        f"Structure {structure.pk}: {exc} Left unchanged for retry."
                    )
                    if consecutive_errors >= options["max_consecutive_errors"]:
                        stopped_at = structure.pk
                        break
                    continue
                consecutive_errors = 0

            if not options["dry_run"]:
                with transaction.atomic():
                    updates = {"canonical_smiles": identity}
                    if not options["index_only"]:
                        updates["names_checked_at"] = timezone.now()
                        updates["iupac_name"] = result["iupac_name"] if result else ""
                        updates["pubchem_cid"] = result["cid"] if result else None
                    # Guard against a concurrent edit while the API call was in flight.
                    changed = Structure.objects.filter(
                        pk=structure.pk, smiles=structure.smiles,
                        adjacency_list=structure.adjacency_list,
                        multiplicity=structure.multiplicity, isomer_id=structure.isomer_id,
                    ).update(**updates)
                    if not changed:
                        skipped += 1
                        continue
                    if not options["index_only"]:
                        structure.names.all().delete()
                        if result:
                            StructureName.objects.bulk_create([
                                StructureName(structure=structure, name=name)
                                for name in result["synonyms"]
                            ])
            indexed += 1
            if result:
                if result["iupac_name"] or result["synonyms"]:
                    named += 1
                if result["iupac_name"]:
                    label = result["iupac_name"]
                elif result["synonyms"]:
                    label = f"{len(result['synonyms'])} synonyms (no IUPAC name)"
                else:
                    label = f"PubChem CID {result['cid']} (no name available)"
                self.stdout.write(f"Structure {structure.pk}: {label}")
        mode = "Would index" if options["dry_run"] else "Indexed"
        self.stdout.write(
            f"{mode} {indexed} structures; named {named}; skipped {skipped}; failed {failed}."
        )
        if failed:
            status = (
                f"Stopped at structure {stopped_at} "
                f"after {consecutive_errors} consecutive failures."
                if stopped_at is not None else f"Finished with {failed} failed lookup(s)."
            )
            self.stderr.write("Previously saved progress has been preserved.")
            raise CommandError(
                f"{status} Rerun enrich_species_names to retry unresolved records"
                " (include --refresh again if this was a refresh run)."
            )
