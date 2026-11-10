"""Give the datasets of renamed ChemKED files their new paths: the same rows and ids.

``sync_chemked`` keys a dataset by its file's repository path. A renamed file would get a new
dataset, and ``prune_chemked_datasets`` would delete the old one: its simulation runs would stay
without a dataset, and its model coverage, species mappings and SSSOM links would go. This
command finds the files that git sees renamed between a commit and the checkout's HEAD and
moves their datasets:

- same content (git R100): only the path changes. The datapoints stay, with the links of their
  simulation results;
- changed content under the same file name (a move to another folder): the moved dataset is
  re-ingested from the file, as a file edited in place is;
- changed content and another file name: not taken for a rename, because git also pairs
  different experiments of similar text. The old dataset goes with the prune and the file gets
  a new one.

A dataset that an ingest already stored at the new path is replaced by the moved one if nothing
outside the ChemKED tables refers to it. The chemked-ingest workflow does the same step with
``sync_chemked --renamed-since``.

Usage, before prune_chemked_datasets after a pull request that moves files:
    python manage.py rename_chemked_datasets --path <checkout> --since <commit before the merge>   # dry run
    python manage.py rename_chemked_datasets --path <checkout> --since <commit> --apply --report renamed.csv

The dry run makes the same changes in a transaction that is rolled back, so its counts are the
ones --apply gives.
"""
import csv
from collections import Counter
from pathlib import Path

import yaml
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chemked_database.management.commands.sync_chemked import (
    ALREADY_MOVED,
    BOTH_PATHS,
    MOVED,
    MOVED_CHANGED,
    NO_DATASET,
    NOT_SAME_FILE,
    move_renamed_datasets,
    store_chemked_data,
)

SimulationRun = apps.get_model("analysis", "SimulationRun")


class Command(BaseCommand):
    help = "Move the datasets of ChemKED files renamed since a commit to their new paths, keeping their ids."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=getattr(settings, "CHEMKED_DATABASE_PATH", None),
            help="ChemKED-database clone, checked out at the commit the database must match (main).",
        )
        parser.add_argument("--since", required=True, metavar="COMMIT", help="Commit the database matches now.")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="CSV file with one row per renamed file.")

    def handle(self, *args, **options):
        if not options["path"] or not Path(options["path"]).is_dir():
            raise CommandError("Give --path, a ChemKED-database clone, or set CHEMKED_DATABASE_PATH.")
        base = Path(options["path"])

        failed = 0
        with transaction.atomic():
            moves = move_renamed_datasets(base, options["since"], self.stdout.write)
            for old, new, similarity, outcome, dataset_id in moves:
                if outcome in (NOT_SAME_FILE, BOTH_PATHS):
                    self.stdout.write(f"  {old} -> {new} (R{similarity:03d}): {outcome}")
                if outcome != MOVED_CHANGED:
                    continue
                try:
                    data = yaml.safe_load((base / new).read_text(encoding="utf-8"))
                    store_chemked_data(data, new, self.stderr.write)
                except (OSError, ValueError, yaml.YAMLError) as exc:
                    # The dataset is at its new path with the old content, as after a failed re-ingest
                    self.stderr.write(f"Failed to re-ingest {new}: {exc}")
                    failed += 1

            outcomes = Counter(outcome for _, _, _, outcome, _ in moves)
            moved = [dataset_id for _, _, _, outcome, dataset_id in moves if outcome in (MOVED, MOVED_CHANGED)]
            runs = Counter(
                SimulationRun.objects.filter(dataset_id__in=[d for _, _, _, _, d in moves if d])
                .values_list("dataset_id", flat=True)
            )
            self.stdout.write(f"Files renamed from {options['since']} to HEAD in {base}: {len(moves)}")
            for outcome in (MOVED, MOVED_CHANGED, ALREADY_MOVED, NO_DATASET, NOT_SAME_FILE, BOTH_PATHS):
                self.stdout.write(f"  {outcomes[outcome]} {outcome}")
            self.stdout.write(
                f"The {len(moved)} moved datasets keep their ids and {sum(runs[d] for d in moved)} simulation runs"
            )

            if options["report"]:
                with open(options["report"], "w", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["dataset_id", "old_path", "new_path", "similarity", "outcome", "simulation_runs"])
                    for old, new, similarity, outcome, dataset_id in moves:
                        writer.writerow([dataset_id or "", old, new, similarity, outcome, runs[dataset_id]])
                self.stdout.write(f"Report: {options['report']}")

            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write("applied" if options["apply"] else "dry run: rolled back, nothing written")
        if failed:
            raise CommandError(f"{failed} moved file(s) were not re-ingested")
