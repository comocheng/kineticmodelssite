from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from database.services.thermo_sources import import_burcat_entry, load_burcat, rmg_database_path


class Command(BaseCommand):
    help = "Import a trusted local RMG Burcat library with explicit structures (default: BurcatNS subset)."

    def add_arguments(self, parser):
        parser.add_argument("--library", help="Trusted RMG Python library; RMG executes this file")
        parser.add_argument("--database-path")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--label", action="append")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be positive.")
        try:
            path = Path(options["library"]) if options["library"] else rmg_database_path(options["database_path"]) / "input/thermo/libraries/BurcatNS.py"
            library, version = load_burcat(path)
            entries = list(library.entries.values())
            if options["label"]:
                missing = set(options["label"]) - {e.label for e in entries}
                if missing:
                    raise CommandError(f"Unknown labels: {', '.join(sorted(missing))}")
                entries = [e for e in entries if e.label in options["label"]]
            if options["limit"]:
                entries = entries[:options["limit"]]
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Library: {library.name}; version {version}. BurcatNS is a curated subset, not the full Burcat database.")
        imported = failed = 0
        for entry in entries:
            try:
                with transaction.atomic():
                    record = import_burcat_entry(library, version, entry)
                    if options["dry_run"]:
                        transaction.set_rollback(True)
                imported += 1
                self.stdout.write(str(record))
            except Exception as exc:
                failed += 1
                self.stderr.write(f"{entry.label}: {exc}")
        self.stdout.write(f"{'Validated (dry run)' if options['dry_run'] else 'Imported'} {imported}; failed {failed}.")
        if failed:
            raise CommandError("Some entries failed. Successful imports are preserved; rerunning is idempotent.")
