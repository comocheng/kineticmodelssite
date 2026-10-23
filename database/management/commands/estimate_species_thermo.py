from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from database.models import Structure
from database.services.thermo_sources import estimate_groups, load_groups


class Command(BaseCommand):
    help = "Estimate gas-phase thermo using only RMG group additivity, retaining source tables and validated NASA fits."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--structure-id", type=int, action="append")
        selection.add_argument("--all", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--database-path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be positive.")
        structures = Structure.objects.select_related("isomer").order_by("id")
        if options["structure_id"]:
            structures = structures.filter(pk__in=options["structure_id"])
            missing = set(options["structure_id"]) - set(structures.values_list("pk", flat=True))
            if missing:
                raise CommandError(f"Unknown structure IDs: {sorted(missing)}")
        structures = structures.filter(pk__gt=options["after_id"])
        if options["limit"]:
            structures = structures[:options["limit"]]
        try:
            database, version = load_groups(options["database_path"])
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        imported = failed = 0
        for structure in structures.iterator():
            try:
                with transaction.atomic():
                    record = estimate_groups(structure, database, version)
                    if options["dry_run"]:
                        transaction.set_rollback(True)
                imported += 1
                self.stdout.write(f"Structure {structure.pk}: {record}")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Structure {structure.pk}: {exc}")
        self.stdout.write(f"{'Validated (dry run)' if options['dry_run'] else 'Estimated'} {imported}; failed {failed}.")
        if failed:
            raise CommandError("Some estimates failed. Successful records are preserved; rerunning is idempotent.")
