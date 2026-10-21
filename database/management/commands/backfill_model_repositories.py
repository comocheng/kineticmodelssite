"""Backfill ``KineticModel.repository_url`` from the RMG-models GitHub repo.

Every kinetic model imported from ``comocheng/RMG-models`` stores its repo-
relative path as ``model_name`` (e.g. ``PCI2013/325-Husson``). This command
turns that into a resolvable GitHub tree URL so the model gains a FAIR I3
repository identifier:

    https://github.com/comocheng/RMG-models/tree/master/<model_name>

By default each candidate path is verified against a local RMG-models checkout
(``--repo-root``) so only models that actually exist in the repo are linked;
pass ``--no-verify`` to skip that check. Idempotent: a row is saved only when its
``repository_url`` changes.

Follow-up: ``generate_model_sssom`` then emits ``promkm:`` rows for the populated
URLs, ``import_sssom`` loads them, and ``link_semantic_mappings`` attaches the
``SemanticMapping.kinetic_model`` foreign keys.
"""

from pathlib import Path
from urllib.parse import quote

from django.core.management.base import BaseCommand

from database.models import KineticModel

DEFAULT_BASE = "https://github.com/comocheng/RMG-models"
DEFAULT_BRANCH = "master"
# RMG-models lives at the workspace root, three levels above this Django project.
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4] / "RMG-models"


class Command(BaseCommand):
    help = "Set KineticModel.repository_url from the RMG-models repo path (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--base", default=DEFAULT_BASE, help="GitHub repo base URL.")
        parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch/ref for tree URLs.")
        parser.add_argument(
            "--repo-root",
            default=str(DEFAULT_REPO_ROOT),
            help="Local RMG-models checkout used to verify each model path exists.",
        )
        parser.add_argument(
            "--no-verify",
            action="store_true",
            help="Build URLs without checking the local checkout for the directory.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing non-empty repository_url values.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        base = options["base"].rstrip("/")
        branch = options["branch"].strip("/")
        repo_root = Path(options["repo_root"])
        verify = not options["no_verify"]
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]

        if verify and not repo_root.is_dir():
            self.stderr.write(
                self.style.ERROR(
                    f"RMG-models checkout not found: {repo_root}. "
                    "Pass --repo-root or --no-verify."
                )
            )
            return

        updated = skipped = missing = unchanged = 0
        for km in KineticModel.objects.all().order_by("model_name"):
            name = (km.model_name or "").strip().strip("/")
            if not name:
                skipped += 1
                continue
            if verify and not (repo_root / name).is_dir():
                missing += 1
                self.stderr.write(f"No repo dir for {km.id} {name!r}; skipping.")
                continue
            if km.repository_url and not overwrite:
                skipped += 1
                continue

            # Encode each path segment but keep the path separators.
            encoded = "/".join(quote(seg) for seg in name.split("/"))
            url = f"{base}/tree/{branch}/{encoded}"
            if km.repository_url == url:
                unchanged += 1
                continue

            if dry_run:
                self.stdout.write(f"{km.id} {name} -> {url}")
            else:
                km.repository_url = url
                km.save(update_fields=["repository_url"])
            updated += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}repository_url backfill -> updated {updated}, "
                f"unchanged {unchanged}, skipped {skipped}, missing-dir {missing}."
            )
        )
