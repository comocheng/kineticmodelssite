"""Give each model's rates the digits its authors wrote, where its RMG-models library rounded them.

RMG-models wrote the libraries with 6 significant digits, so PCI2017/051-Pelucchi's Ea 45025.57 cal/mol was
stored as 45025.6. This reads each model's CHEMKIN file (the --reactions file of its import.sh in RMG-models),
pairs its lines with the model's links, and gives a stored number that is the author's number rounded to 6
digits the author's number; see database/scripts/author_digits.py. A record that several models share keeps
its numbers for the models whose lines give them; the others move to a record with their numbers. The
importer does the same for every model it imports.

Usage:
    python manage.py restore_author_digits --report digits.json          # dry run
    python manage.py restore_author_digits --apply --report digits.json
    python manage.py restore_author_digits --apply --model PCI2017/051-Pelucchi
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from database import models as db
from database.scripts import author_digits
from database.services.cleanup import MODELS


class Command(BaseCommand):
    help = "Give the models' rates the digits of their CHEMKIN files where the libraries rounded them."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=settings.RMG_MODELS_PATH, help="RMG-models directory")
        parser.add_argument("--model", action="append", help="Model name (repeatable); default: every model")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="Write the report (JSON) to this file.")

    def handle(self, *args, **options):
        wanted = set(options["model"] or [])
        models = [(model, os.path.join(options["path"], model.model_name))
                  for model in db.KineticModel.objects.order_by("model_name")
                  if not wanted or model.model_name in wanted]
        report = author_digits.restore(models, MODELS, apply=options["apply"])
        for row in report["models"]:
            if row["numbers"] or row["other"]:
                numbers = ", ".join(f"{k} {v}" for k, v in sorted(row["numbers"].items()))
                self.stdout.write(f"{row['model']}: {row['lines'].get('paired', 0)} lines paired; "
                                  f"{row['links']} links; {numbers}")
        if options["report"]:
            with open(options["report"], "w") as handle:
                json.dump(report, handle, indent=1, sort_keys=True)
        self.stdout.write(f"numbers {sum(report['numbers'].values())} ({dict(sorted(report['numbers'].items()))}); "
                          f"other differences kept {dict(sorted(report['other'].items()))}; links {report['links']}, "
                          f"moved {report['links_moved']}; records {dict(sorted(report['records'].items()))}")
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
