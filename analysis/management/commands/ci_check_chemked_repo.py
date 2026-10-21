"""
Management command: check the ChemKED files of a ChemKED-database pull request
for duplicate data and for the folder they belong in, and post the result back
to the pull request as a check-run.

Called by the ``pyked-ci-validate`` GitHub Actions workflow after the PyKED
validation, with the pull request's files decoded at their repo paths. The
files are compared with the local ChemKED-database clone
(``CHEMKED_DATABASE_PATH``) by chemked_database.repo_check, the same check the
web upload uses:

* failure: a file holds the same data as a committed file (in any folder,
  under any name) or as another file of the pull request;
* warning: a new file is not in the folder that the existing layout gives
  (folder of files with the same fuels, then of the same paper, then
  ``Author_Year``). A file with the same name in another folder is fine.

Usage::

    python manage.py ci_check_chemked_repo \
        --files-dir /tmp/pyked_ci_files \
        --pr-repo LekiaAnonim/ChemKED-database \
        --pr-number 1 \
        --commit-sha abc123def456

Use ``--no-check-run`` to print the result without posting it.
"""

import glob
import os
import subprocess
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from analysis.management.commands.ci_validate_chemked import (
    _create_check_run,
    _update_check_run,
)
from chemked_database.repo_check import data_key, load_chemked, load_index

CHECK_RUN_NAME = "ChemKED Duplicate and Folder Check"
ICONS = {"failure": "❌", "warning": "⚠️", "notice": "✅"}


def check_files(index, files):
    """Check {repo path: content} against *index*.

    Returns a list of (path, level, message), level 'failure', 'warning' or
    'notice'.
    """
    results = []
    by_data = defaultdict(list)
    for path, content in sorted(files.items()):
        data = load_chemked(content)
        if data is None:
            results.append((path, "notice", "Not a ChemKED YAML mapping; not checked."))
            continue
        key = data_key(data)
        if key:
            by_data[key].append(path)

        is_new = path not in index.files
        match = index.find_duplicate(content, exclude_path=path)
        if match:
            same = "Identical to" if match.kind == "exact" else "Same data as"
            hint = (
                " Update that file instead of adding a copy (if this pull request "
                "moves that file, this is expected)." if is_new else ""
            )
            results.append((path, "failure", f"{same} `{match.path}`.{hint}"))
            continue

        if not is_new:
            results.append((path, "notice", "Update of a committed file; no duplicate data."))
            continue
        suggestion = index.suggest_folder(content)
        directory = os.path.dirname(path)
        if directory == suggestion.directory:
            results.append((path, "notice", f"New file in the expected folder `{directory}/`."))
        else:
            results.append((
                path, "warning",
                f"Expected folder `{suggestion.directory}/`, not `{directory or '.'}/`: "
                f"{suggestion.reason}.",
            ))

    for paths in by_data.values():
        for path in paths if len(paths) > 1 else ():
            others = ", ".join(f"`{other}`" for other in paths if other != path)
            results.append((path, "failure", f"Same data as {others} in this pull request."))
    return results


def _summary(results, index):
    counts = {level: sum(1 for _, lv, _ in results if lv == level) for level in ICONS}
    lines = [
        f"## {CHECK_RUN_NAME}\n",
        f"Compared with ChemKED-database commit `{index.commit[:12]}` "
        f"({len(index.files)} files).\n",
        f"**{counts['failure']}** duplicate(s), **{counts['warning']}** folder warning(s)\n",
        "| Result | File | Details |",
        "|--------|------|---------|",
    ]
    for path, level, message in results:
        lines.append(f"| {ICONS[level]} | `{path}` | {message} |")
    return "\n".join(lines)


class Command(BaseCommand):
    help = (
        "Check contributed ChemKED files for duplicate data and folder placement "
        "against the local ChemKED-database clone, and post a check-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--files-dir", required=True,
            help="Directory with the pull request's YAML files at their repo paths.",
        )
        parser.add_argument(
            "--clone", default=getattr(settings, "CHEMKED_DATABASE_PATH", None),
            help="ChemKED-database clone to compare with (default: CHEMKED_DATABASE_PATH).",
        )
        parser.add_argument(
            "--pull", action="store_true",
            help="Run 'git pull --ff-only' in the clone first.",
        )
        parser.add_argument("--pr-repo", default="", help="owner/name of the pull request's repo.")
        parser.add_argument("--pr-number", type=int, default=0, help="Pull request number.")
        parser.add_argument("--commit-sha", default="", help="Commit SHA for the check-run.")
        parser.add_argument(
            "--github-token", default="",
            help="GitHub token override (defaults to GITHUB_TOKEN setting).",
        )
        parser.add_argument(
            "--no-check-run", action="store_true",
            help="Print the result only; do not post a check-run.",
        )

    def handle(self, *args, **options):
        files_dir = options["files_dir"]
        clone = options["clone"]
        if not os.path.isdir(files_dir):
            raise CommandError(f"Directory not found: {files_dir}")

        if options["pull"] and clone:
            pulled = subprocess.run(
                ["git", "-C", clone, "pull", "--ff-only"], capture_output=True, text=True
            )
            if pulled.returncode != 0:
                self.stderr.write(f"git pull in {clone} failed: {pulled.stderr.strip()}")

        index = load_index(clone)
        if index is None:
            raise CommandError(f"No ChemKED-database git clone at {clone!r}; set CHEMKED_DATABASE_PATH.")

        files = {}
        for pattern in ("*.yaml", "*.yml"):
            for filepath in glob.glob(os.path.join(files_dir, "**", pattern), recursive=True):
                with open(filepath, "rb") as fh:
                    files[os.path.relpath(filepath, files_dir)] = fh.read()
        if not files:
            self.stdout.write(self.style.WARNING(f"No YAML files found in {files_dir}"))
            return

        results = check_files(index, files)
        for path, level, message in results:
            style = {"failure": self.style.ERROR, "warning": self.style.WARNING}.get(
                level, self.style.SUCCESS
            )
            self.stdout.write(style(f"  [{level.upper()}] {path} — {message}"))

        failures = sum(1 for _, level, _ in results if level == "failure")
        warnings = sum(1 for _, level, _ in results if level == "warning")
        conclusion = "failure" if failures else ("neutral" if warnings else "success")
        title = f"{failures} duplicate(s), {warnings} folder warning(s) in {len(files)} file(s)"
        self.stdout.write(f"\n{conclusion}: {title}")
        if options["no_check_run"]:
            return

        token = (
            options["github_token"]
            or getattr(settings, "GITHUB_TOKEN", "")
            or os.getenv("GITHUB_TOKEN", "")
        )
        if not (token and options["pr_repo"] and options["commit_sha"]):
            raise CommandError("--pr-repo, --commit-sha and a GitHub token are needed for the check-run.")
        check_run_id = _create_check_run(
            options["pr_repo"], options["commit_sha"], token,
            pr_number=options["pr_number"], name=CHECK_RUN_NAME,
        )
        _update_check_run(
            options["pr_repo"], check_run_id,
            conclusion=conclusion,
            title=title,
            summary=_summary(results, index),
            annotations=[
                {
                    "path": path, "start_line": 1, "end_line": 1,
                    "annotation_level": level, "title": CHECK_RUN_NAME, "message": message,
                }
                for path, level, message in results if level != "notice"
            ],
            token=token,
        )
