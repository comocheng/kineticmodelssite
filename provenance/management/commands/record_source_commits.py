"""Fills in the source commit of the kinetic models and ChemKED datasets that were read before the
importers recorded it: the last commit that changed each model's folder in RMG-models, or each
dataset's file in the ChemKED database (provenance.git_sources).

Use it only with the clones the records were read from, at the state they were read in: the
command cannot tell whether the files changed since. Records whose files have uncommitted changes
get no commit.

    python manage.py record_source_commits                 # dry run: counts what would change
    python manage.py record_source_commits --apply
    python manage.py record_source_commits --apply --all   # also replace commits already recorded

Run assign_record_keys --apply afterwards, so that the snapshots of the kinetics and thermo keys
name the commits.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from chemked_database.models import ExperimentDataset
from database.models import KineticModel
from provenance.git_sources import Checkout


class Command(BaseCommand):
    help = "Fill in the RMG-models and ChemKED-database commits that the models and datasets were read from."

    def add_arguments(self, parser):
        parser.add_argument("--rmg-models", default=settings.RMG_MODELS_PATH, help="RMG-models clone")
        parser.add_argument("--chemked", default=getattr(settings, "CHEMKED_DATABASE_PATH", ""),
                            help="ChemKED-database clone")
        parser.add_argument("--apply", action="store_true", help="Write the commits (default: dry run).")
        parser.add_argument("--all", action="store_true", help="Also replace commits already recorded.")

    def handle(self, *args, **options):
        self.fill("models", KineticModel.objects.order_by("model_name"), "model_name",
                  options["rmg_models"], options)
        self.fill("datasets", ExperimentDataset.objects.order_by("chemked_file_path"), "chemked_file_path",
                  options["chemked"], options)
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")

    def fill(self, label, records, path_field, root, options):
        if not root or not Path(root).is_dir():
            self.stdout.write(f"{label}: no clone at {root!r}; skipped")
            return
        checkout = Checkout(root)
        if checkout.root is None:
            self.stdout.write(f"{label}: {root} is not a git clone; skipped")
            return
        counts = {"set": 0, "changed": 0, "unchanged": 0, "kept": 0, "no file": 0, "no commit": 0}
        changes = []
        for record in records.only("pk", path_field, "source_commit"):
            if record.source_commit and not options["all"]:
                counts["kept"] += 1
                continue
            path = Path(root) / getattr(record, path_field)
            if not path.exists():
                counts["no file"] += 1
                continue
            commit = checkout.commit(path)
            if not commit:
                counts["no commit"] += 1
            elif commit == record.source_commit:
                counts["unchanged"] += 1
            else:
                counts["changed" if record.source_commit else "set"] += 1
                changes.append((record.pk, commit))
        if options["apply"]:
            model = records.model
            for pk, commit in changes:
                model.objects.filter(pk=pk).update(source_commit=commit)
        self.stdout.write(f"{label} ({checkout.root}): " + ", ".join(f"{k} {v}" for k, v in counts.items()))
