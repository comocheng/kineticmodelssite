"""Give each model's Chebyshev rates the model's own T and P range (TCHEB, PCHEB).

The range of a Chebyshev rate makes its reduced T and P, so it is part of the rate. An earlier
importer gave a model that writes another model's coefficients with another range the record (and
range) of the model imported first. This reads each linking model's RMG-models library and moves
the links of a record whose models give other ranges to a record with their own range; see
database/services/chebyshev_ranges.py. The importer now keeps the range in the identity.

Usage:
    python manage.py split_chebyshev_ranges --report ranges.json          # dry run: does the work and rolls it back
    python manage.py split_chebyshev_ranges --apply --report ranges.json
    python manage.py split_chebyshev_ranges --apply --model PCI2017/111-Jin
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from database.services.chebyshev_ranges import split_chebyshev_ranges
from database.models import KineticModel
from database.scripts.import_rmg_models import record_source_commits
from database.services.cleanup import MODELS


class Command(BaseCommand):
    help = "Give each model's Chebyshev rates the model's own T and P range."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=settings.RMG_MODELS_PATH, help="RMG-models directory")
        parser.add_argument("--model", action="append", help="Model name (repeatable); default: every model")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="Write the counts and each changed record to this JSON file.")

    def handle(self, *args, **options):
        wanted = set(options["model"] or [])
        report = split_chebyshev_ranges(options["path"], apply=options["apply"], models=wanted)
        if options["apply"]:
            record_source_commits([(model, os.path.join(options["path"], model.model_name))
                                   for model in KineticModel.objects.all()
                                   if not wanted or model.model_name in wanted], MODELS)
        for row in report["records"]:
            kept = f"kept {row['kept']['range']} ({', '.join(row['kept']['models'])})" if row["kept"] else "kept none"
            moved = "; ".join(f"{m['range']} ({', '.join(m['models'])}) to {'new ' if m['new'] else ''}record {m['to']}"
                              for m in row["moved"])
            self.stdout.write(f"record {row['kinetics_id']}, stored {row['stored']}: {kept}; {moved}")
        if options["report"]:
            with open(options["report"], "w") as handle:
                json.dump(report, handle, indent=1)
        self.stdout.write(", ".join(f"{k} {v}" for k, v in report["counts"].items()))
        if report["notes"]:
            self.stdout.write("own ranges: " + ", ".join(f"{k} {v}" for k, v in report["notes"].items()))
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
