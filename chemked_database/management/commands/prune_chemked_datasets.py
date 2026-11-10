"""Delete the ChemKED datasets whose file is not in a ChemKED-database checkout.

The database holds the files of the ChemKED-database main branch and nothing else. Two kinds
of dataset have no file there:

- datasets that the web pages stored directly, before every data entry route went through a
  pull request. Their names are flat (``CH4_Asaba_1963_ST_10004084``), not repository paths;
- datasets of files that were moved, renamed or deleted in the repository, or that came from
  another branch.

``sync_chemked`` stores a file under its repository path, so such a dataset would stay as a
second copy of the experiment. After a pull request that renames files, run
``rename_chemked_datasets`` first: it moves their datasets to the new paths, so that the prune
deletes only the datasets of deleted files. The command also deletes the compositions,
composition species and values with units that no row uses: before sync_chemked replaced them
on re-ingest, every re-ingest left the old ones behind.

Usage:
    python manage.py prune_chemked_datasets --path <ChemKED-database checkout>   # dry run
    python manage.py prune_chemked_datasets --path <checkout> --apply --report deleted.csv
    python manage.py prune_chemked_datasets --path <checkout> --apply --with-runs   # their runs too

The dry run makes the same deletions in a transaction that is rolled back, so its counts are
the ones --apply gives.
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import transaction
from django.db.models import Count

from chemked_database.management.commands.sync_chemked import (
    delete_unused_compositions,
    delete_unused_values,
)
from chemked_database.models import CompositionSpecies, ExperimentDataset

SimulationRun = apps.get_model("analysis", "SimulationRun")

FLAT = "flat name (stored by the web pages)"
NOT_IN_CHECKOUT = "repository path not in the checkout"


def stale_datasets(files):
    """Datasets whose chemked_file_path is not one of *files*, with their kind."""
    stale = (
        ExperimentDataset.objects.exclude(chemked_file_path__in=files)
        .annotate(n_datapoints=Count("datapoints", distinct=True))
        .order_by("chemked_file_path")
    )
    return [(d, FLAT if "/" not in d.chemked_file_path else NOT_IN_CHECKOUT) for d in stale]


class Command(BaseCommand):
    help = "Delete ChemKED datasets whose file is not in a ChemKED-database checkout, and unused rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=getattr(settings, "CHEMKED_DATABASE_PATH", None),
            help="ChemKED-database checkout of the branch the database must match (main).",
        )
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="CSV file with one row per dataset to delete.")
        parser.add_argument(
            "--with-runs",
            action="store_true",
            help="Delete the simulation runs of the deleted datasets too (default: they stay, without a dataset).",
        )

    def handle(self, *args, **options):
        if not options["path"] or not Path(options["path"]).is_dir():
            raise CommandError("Give --path, a ChemKED-database checkout, or set CHEMKED_DATABASE_PATH.")
        base = Path(options["path"])
        # The paths sync_chemked gives the datasets it stores
        files = {str(p.relative_to(base)) for p in base.rglob("*.yaml")}
        if not files:
            raise CommandError(f"No YAML file under {base}: every dataset would be deleted.")

        stored = ExperimentDataset.objects.count()
        stale = stale_datasets(files)
        self.stdout.write(f"ChemKED-database checkout {base}: {len(files)} YAML files")
        self.stdout.write(
            f"Datasets: {stored} stored, {stored - len(stale)} with a file in the checkout, "
            f"{len(stale)} without"
        )
        for kind in (FLAT, NOT_IN_CHECKOUT):
            self.stdout.write(f"  {sum(1 for _, k in stale if k == kind)} with a {kind}")

        if options["report"]:
            with open(options["report"], "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "chemked_file_path", "kind", "experiment_type", "datapoints", "created_at"])
                for dataset, kind in stale:
                    writer.writerow([
                        dataset.pk, dataset.chemked_file_path, kind, dataset.experiment_type,
                        dataset.n_datapoints, dataset.created_at.isoformat(),
                    ])
            self.stdout.write(f"Report: {options['report']}")

        with transaction.atomic():
            ids = [d.pk for d, _ in stale]
            runs = SimulationRun.objects.filter(dataset_id__in=ids)
            run_count = runs.count()
            if options["with_runs"]:
                _, deleted_runs = runs.delete()
                for label, count in sorted(deleted_runs.items()):
                    self.stdout.write(f"  deleted {label}: {count}")
            # The species of profiles belong to no composition, so they go first
            CompositionSpecies.objects.filter(
                concentration_profiles__measurement__datapoint__dataset__in=ids
            ).delete()
            _, deleted = ExperimentDataset.objects.filter(pk__in=ids).delete()
            compositions, species = delete_unused_compositions()
            # Species rows of neither a composition nor a profile
            _, loose = CompositionSpecies.objects.filter(
                composition__isnull=True, concentration_profiles__isnull=True
            ).delete()
            values = delete_unused_values()

            for label, count in sorted(deleted.items()):
                self.stdout.write(f"  deleted {label}: {count}")
            self.stdout.write(
                f"Unused rows deleted: {compositions} compositions with {species} species, "
                f"{loose.get(CompositionSpecies._meta.label, 0)} species of no composition or profile, "
                f"{values} values with units"
            )
            if run_count and not options["with_runs"]:
                self.stdout.write(
                    f"{run_count} simulation runs were on the deleted datasets; they stay, without a "
                    "dataset (--with-runs deletes them)"
                )
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write("applied" if options["apply"] else "dry run: rolled back, nothing written")
