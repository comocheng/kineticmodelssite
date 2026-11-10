"""Replace each model's species names, thermo links and kinetics links with what the current
importer makes from the model's RMG libraries.

This removes links that older imports made and the current importer does not: a name on the
wrong record (OH* on ground-state OH), a second link to the same thermo row, a link to a thermo
provider's copy. An old link is kept when the library entry that would replace it fails to
import. Each model is one transaction. Run after merge_split_species.

Usage:
    python manage.py rebuild_model_links --report rebuild.jsonl          # dry run
    python manage.py rebuild_model_links --apply --report rebuild.jsonl
    python manage.py rebuild_model_links --apply --model GRI-mech-3.0
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from database.management.commands.import_rmg_models import get_models
from database.models import KineticModel
from database.services.cleanup import rebuild_model_links


class Command(BaseCommand):
    help = "Rebuild each model's names, thermo links and kinetics links from its RMG libraries."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=settings.RMG_MODELS_PATH, help="RMG-models directory")
        parser.add_argument("--model", action="append", help="Model name (repeatable); default: every model")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="Write one JSON line per model to this file.")

    def handle(self, *args, **options):
        models = {m.model_name: m for m in KineticModel.objects.all()}
        wanted = set(options["model"] or models)
        report = open(options["report"], "a") if options["report"] else None
        found = set()
        for name, thermo_path, kinetics_path, _ in get_models(options["path"], ["PCI2011/193-Mehl"]):
            if name not in wanted or name not in models:
                continue
            found.add(name)
            with transaction.atomic():
                result = rebuild_model_links(models[name], thermo_path, kinetics_path)
                if not options["apply"]:
                    transaction.set_rollback(True)
            self.stdout.write(
                f"{name}: names {result['names']}, thermo links {result['thermo_links']}, "
                f"kinetics links {result['kinetics_links']}")
            if report:
                report.write(json.dumps(result, default=list) + "\n")
                report.flush()
        for name in sorted(wanted - found):
            self.stdout.write(self.style.WARNING(f"{name}: no libraries in {options['path']}; links left as they are"))
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
