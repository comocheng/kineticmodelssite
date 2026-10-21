"""Backfill ``ExperimentDataset.data_repository_url`` from the ChemKED-database repo.

The kinetic-model side derives a GitHub URL trivially because each model name is
its repo path. ChemKED datasets are messier: ``chemked_file_path`` is sometimes a
real repo-relative path (``methane/Grillo_1976/x10004387.yaml``) and sometimes a
flat ReSpecTh-style name (``CH4_Asaba_1963_ST_10004084``) whose only stable key is
the trailing ReSpecTh id (the file on disk is ``.../Asaba_1963/x10004084.yaml``).

This command resolves each dataset to a real file in a local ChemKED-database
checkout using two HIGH-CONFIDENCE tiers only, then writes a blob URL:

    <base>/blob/<branch>/<resolved-relative-path>

  1. exact relative-path match (with/without .yaml) -> certain.
  2. canonical ReSpecTh id (>= 7 digits) that is unique in the repo -> certain.

Datasets whose path is truncated/ambiguous (short ids, no file) are left blank and
reported -- a wrong provenance URL is worse than none. Idempotent: a row is saved
only when ``data_repository_url`` changes.
"""

import re
from pathlib import Path
from urllib.parse import quote

from django.core.management.base import BaseCommand

from chemked_database.models import ExperimentDataset

DEFAULT_BASE = "https://github.com/LekiaAnonim/ChemKED-database"
DEFAULT_BRANCH = "Prosper_WIP"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4] / "ChemKED-database"
CANONICAL_ID = re.compile(r"\d{7,}")


def _canonical_id(text):
    """Longest >=7-digit token (the ReSpecTh id), ignoring years/short numbers."""
    nums = CANONICAL_ID.findall(text or "")
    return max(nums, key=len) if nums else None


class Command(BaseCommand):
    help = "Set ExperimentDataset.data_repository_url from the ChemKED-database repo (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--base", default=DEFAULT_BASE, help="GitHub repo base URL.")
        parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch/ref for blob URLs.")
        parser.add_argument(
            "--repo-root",
            default=str(DEFAULT_REPO_ROOT),
            help="Local ChemKED-database checkout used to resolve dataset files.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing non-empty data_repository_url values.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report matches without writing to the database.",
        )

    def handle(self, *args, **options):
        base = options["base"].rstrip("/")
        branch = options["branch"].strip("/")
        repo_root = Path(options["repo_root"])
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]

        if not repo_root.is_dir():
            self.stderr.write(
                self.style.ERROR(f"ChemKED-database checkout not found: {repo_root}.")
            )
            return

        by_rel = {}
        by_id = {}
        id_collisions = set()
        for p in repo_root.rglob("*.y*ml"):
            if ".git" in p.parts:
                continue
            rel = p.relative_to(repo_root).as_posix()
            by_rel[rel.lower()] = rel
            cid = _canonical_id(p.stem)
            if cid:
                if cid in by_id and by_id[cid] != rel:
                    id_collisions.add(cid)
                by_id.setdefault(cid, rel)
        for cid in id_collisions:
            by_id.pop(cid, None)  # ambiguous ids are unusable

        def resolve(raw):
            low = raw.lower()
            for cand in (low, f"{low}.yaml", f"{low}.yml"):
                if cand in by_rel:
                    return by_rel[cand], "rel"
            cid = _canonical_id(raw)
            if cid and cid in by_id:
                return by_id[cid], "id"
            return None, None

        updated = unchanged = skipped = unresolved = 0
        by_rel_hits = by_id_hits = 0
        unresolved_samples = []
        for ds in ExperimentDataset.objects.exclude(chemked_file_path=""):
            rel, how = resolve(ds.chemked_file_path)
            if rel is None:
                unresolved += 1
                if len(unresolved_samples) < 15:
                    unresolved_samples.append(ds.chemked_file_path)
                continue
            if how == "rel":
                by_rel_hits += 1
            else:
                by_id_hits += 1
            if ds.data_repository_url and not overwrite:
                skipped += 1
                continue
            encoded = "/".join(quote(seg) for seg in rel.split("/"))
            url = f"{base}/blob/{branch}/{encoded}"
            if ds.data_repository_url == url:
                unchanged += 1
                continue
            if dry_run:
                self.stdout.write(f"{ds.id} {ds.chemked_file_path}  ->  {rel}")
            else:
                ds.data_repository_url = url
                ds.save(update_fields=["data_repository_url"])
            updated += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}data_repository_url backfill -> updated {updated} "
                f"(exact-path {by_rel_hits}, id {by_id_hits}), "
                f"unchanged {unchanged}, skipped {skipped}, unresolved {unresolved}."
            )
        )
        if unresolved_samples:
            self.stdout.write("Unresolved (truncated/ambiguous path) examples:")
            for s in unresolved_samples:
                self.stdout.write(f"  {s}")
