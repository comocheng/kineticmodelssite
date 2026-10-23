"""
Management command to rebuild the Fuel-Model Compatibility Map.

Usage::

    python manage.py rebuild_fuel_map
    python manage.py rebuild_fuel_map --keep-existing
    python manage.py rebuild_fuel_map --models "Model 1" "Model 2"
"""

import time
from django.core.management.base import BaseCommand

from database.models import KineticModel
from analysis.services.fuel_model_map import rebuild_fuel_map


class Command(BaseCommand):
    help = (
        "Rebuild the Fuel-Model Compatibility Map by scanning all experiment "
        "datasets for fuel species and checking every kinetic model for "
        "compatibility."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-existing",
            action="store_true",
            help="Do not clear existing compatibility records before rebuilding.",
        )
        parser.add_argument(
            "--models",
            nargs="+",
            help="Only process these kinetic model names (space-separated).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("═" * 60))
        self.stdout.write(self.style.NOTICE(" Fuel-Model Compatibility Map — Rebuild"))
        self.stdout.write(self.style.NOTICE("═" * 60))

        clear = not options["keep_existing"]
        models_qs = None

        if options["models"]:
            model_names = options["models"]
            models_qs = KineticModel.objects.filter(model_name__in=model_names)
            found = models_qs.count()
            self.stdout.write(
                f"Limiting to {found} model(s): {', '.join(model_names)}"
            )
            if found == 0:
                self.stderr.write(self.style.ERROR("No matching models found."))
                return

        def _progress(step, total, msg):
            self.stdout.write(f"  [{step}/{total}] {msg}")

        start = time.time()

        stats = rebuild_fuel_map(
            clear_existing=clear,
            models_qs=models_qs,
            progress_callback=_progress,
        )

        elapsed = time.time() - start

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("═" * 60))
        self.stdout.write(self.style.SUCCESS(" Summary"))
        self.stdout.write(self.style.SUCCESS("═" * 60))
        self.stdout.write(f"  Fuel species found:    {stats['fuels_found']}")
        self.stdout.write(f"  Groups created:        {stats['groups_created']}")
        self.stdout.write(f"  Pairs checked:         {stats['pairs_checked']}")
        self.stdout.write(
            f"  Compatible pairs:      {stats['compatible_pairs']} "
            f"({stats['compatible_pairs'] / max(stats['pairs_checked'], 1) * 100:.1f}%)"
        )
        self.stdout.write(f"  Elapsed time:          {elapsed:.1f}s")
        self.stdout.write(self.style.SUCCESS("═" * 60))
