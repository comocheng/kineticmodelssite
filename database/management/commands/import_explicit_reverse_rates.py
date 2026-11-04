"""Give each model's links the model's explicit reverse rates, REV / A n Ea / on its CHEMKIN lines.

RMG-models keeps only the forward rate of such a line, so the links have no reverse rate and the
exports gave the reverse rate from thermochemistry. This reads each model's CHEMKIN file (the
--reactions file of its import.sh in RMG-models) and sets KineticsComment.reverse_rate; see
database/scripts/explicit_reverse.py. It changes only that field, and clears it on a link that no
REV line gives one. The importer does the same for every model it imports.

Usage:
    python manage.py import_explicit_reverse_rates --report reverse.csv          # dry run
    python manage.py import_explicit_reverse_rates --apply --report reverse.csv
    python manage.py import_explicit_reverse_rates --apply --model CombFlame2013/17-Malewicki
"""
import csv
import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from database import models as db
from database.scripts import explicit_reverse
from database.services.cleanup import MODELS


class Command(BaseCommand):
    help = "Set each model's explicit reverse rates (REV) on its links from its CHEMKIN file."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=settings.RMG_MODELS_PATH, help="RMG-models directory")
        parser.add_argument("--model", action="append", help="Model name (repeatable); default: every model")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="Write one CSV row per REV line to this file.")

    def handle(self, *args, **options):
        wanted = set(options["model"] or [])
        totals, rows = Counter(), []
        for model in db.KineticModel.objects.order_by("model_name"):
            if wanted and model.model_name not in wanted:
                continue
            folder = os.path.join(options["path"], model.model_name)
            with transaction.atomic():
                report = explicit_reverse.attach(model, folder, MODELS, apply=options["apply"])
            rows.extend(report["lines"])
            totals.update(report["status"])
            totals.update({k: report[k] for k in ("set", "cleared", "unchanged")})
            if report["rev_lines"] or report["set"] or report["cleared"]:
                status = ", ".join(f"{k} {v}" for k, v in sorted(report["status"].items()))
                self.stdout.write(f"{model.model_name}: {report['rev_lines']} REV lines ({status}); links set "
                                  f"{report['set']}, cleared {report['cleared']}, unchanged {report['unchanged']}")
        if options["report"]:
            with open(options["report"], "w", newline="") as handle:
                writer = csv.DictWriter(handle, ["model", "line", "status", "kinetics_id", "term", "text", "rev"])
                writer.writeheader()
                writer.writerows(rows)
        self.stdout.write(", ".join(f"{k} {v}" for k, v in sorted(totals.items())))
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
