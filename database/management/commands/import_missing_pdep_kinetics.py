"""Add the pressure-dependent kinetics that earlier imports dropped.

Older converters failed on every PLOG (PDepArrhenius), duplicate-PLOG (MultiPDepArrhenius) and
Chebyshev entry, so imported models lack them. This re-reads each model's RMG-Py kinetics
library and imports only those entries; get_or_create throughout leaves existing rows alone.
"""
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from database import models
from database.management.commands.import_rmg_models import get_models
from database.scripts.import_rmg_models import import_kinetics

PDEP_TYPES = {"PDepArrhenius", "MultiPDepArrhenius", "Chebyshev"}


class Command(BaseCommand):
    help = "Import the PLOG, multi-PLOG and Chebyshev kinetics missing from already-imported models."

    def add_arguments(self, parser):
        parser.add_argument("--model", action="append", help="Model name (repeatable); default: every imported model")
        parser.add_argument("--path", default=settings.RMG_MODELS_PATH, help="RMG-models directory")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        imported = set(models.KineticModel.objects.values_list("model_name", flat=True))
        wanted = set(options["model"] or imported)
        unknown = wanted - imported
        if unknown:
            raise CommandError(f"Not imported yet: {sorted(unknown)}. Use import_rmg_models first.")
        totals = Counter()
        found = set()
        unloadable = []
        with transaction.atomic():
            for name, _, kinetics_path, _ in get_models(options["path"]):
                if name not in wanted or not kinetics_path:
                    continue
                found.add(name)
                model = models.KineticModel.objects.get(model_name=name)
                try:
                    counts = import_kinetics(kinetics_path, model, models, only_types=PDEP_TYPES)
                except Exception as exc:
                    # RMG refuses some whole libraries, e.g. reactions with more than 3 products.
                    unloadable.append(f"{name}: {exc}")
                    continue
                totals.update(counts)
                if counts["imported"] or counts["failed"] or counts["rejected"]:
                    self.stdout.write(f"{name}: {counts['imported']} imported, {counts['failed']} failed, "
                                      f"{counts['rejected']} reactions RMG cannot load")
            if options["dry_run"]:
                transaction.set_rollback(True)
        missing = sorted(wanted - found)
        if missing:
            self.stderr.write(f"No kinetics library under {options['path']} for: {', '.join(missing)}")
        for problem in unloadable:
            self.stderr.write(f"Library not loaded by RMG, skipped: {problem}")
        suffix = " (dry run: nothing saved)" if options["dry_run"] else ""
        self.stdout.write(f"Pressure-dependent entries: {totals['imported']} imported, {totals['failed']} failed; "
                          f"{totals['rejected']} reactions RMG cannot load were skipped{suffix}")
        if totals["failed"]:
            raise CommandError("Some entries failed; see the log for each reaction.")
