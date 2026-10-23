"""
Management command: run PyKED schema validation for a directory of ChemKED
files and post results back to a GitHub pull request as a check-run.

Called by the ``pyked-ci-validate`` GitHub Actions workflow when a
``pyked-validate`` repository_dispatch arrives from ChemKED-database CI.

Usage::

    python manage.py ci_validate_chemked \
        --files-dir /tmp/pyked_ci_files \
        --pr-repo LekiaAnonim/ChemKED-database \
        --pr-number 1 \
        --commit-sha abc123def456
"""

import datetime
import glob
import json
import logging
import os
import urllib.error
import urllib.request

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
CHECK_RUN_NAME = "PyKED Schema Validation"


# ---------------------------------------------------------------------------
# GitHub check-run helpers  (shared pattern with ci_simulate)
# ---------------------------------------------------------------------------

def _gh_headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _api(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_gh_headers(token), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except Exception:
            pass
        logger.error("GitHub API %s %s → %s: %s", method, url, e.code, detail)
        return None


def _create_check_run(pr_repo, commit_sha, token, pr_number=None, name=CHECK_RUN_NAME):
    details_url = (
        f"https://github.com/{pr_repo}/pull/{pr_number}"
        if pr_number else f"https://github.com/{pr_repo}"
    )
    url = f"{GITHUB_API}/repos/{pr_repo}/check-runs"
    result = _api("POST", url, token, {
        "name": name,
        "head_sha": commit_sha,
        "status": "in_progress",
        "started_at": _now(),
        "details_url": details_url,
    })
    check_run_id = result.get("id") if result else None
    logger.info("Created check-run #%s", check_run_id)
    return check_run_id


def _update_check_run(pr_repo, check_run_id, conclusion, title, summary, annotations, token):
    if check_run_id is None:
        return
    url = f"{GITHUB_API}/repos/{pr_repo}/check-runs/{check_run_id}"
    _api("PATCH", url, token, {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": _now(),
        "output": {
            "title": title,
            "summary": summary,
            "annotations": annotations[:50],
        },
    })


# ---------------------------------------------------------------------------
# PyKED validation
# ---------------------------------------------------------------------------

def _validate_file(filepath):
    """Validate a single ChemKED YAML file. Returns (ok, message)."""
    try:
        with open(filepath, "r") as fh:
            data = yaml.safe_load(fh)
    except Exception as e:
        return False, f"YAML parse error: {e}"

    if not isinstance(data, dict):
        return False, "File does not contain a YAML mapping"

    exp_type = (data.get("experiment-type") or "").lower().strip()
    if exp_type in ("rate coefficient", "thermochemical"):
        required = {"file-authors", "reference", "datapoints"}
        missing = required - set(data.keys())
        if missing:
            return False, f"Missing required keys: {', '.join(sorted(missing))}"
        return True, f"OK — {exp_type} data, {len(data.get('datapoints', []))} datapoint(s)"

    from pyked.chemked import ChemKED
    try:
        ck = ChemKED(filepath)
        return True, f"OK — {len(ck.datapoints)} datapoint(s)"
    except Exception as e:
        return False, str(e)


def _build_summary(results):
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    lines = [
        "## PyKED Schema Validation\n",
        f"**{passed}** passed, **{failed}** failed\n",
        "| Status | File | Details |",
        "|--------|------|---------|",
    ]
    for filename, ok, msg in results:
        icon = "✅" if ok else "❌"
        lines.append(f"| {icon} | `{filename}` | {msg} |")
    return "\n".join(lines)


def _build_annotations(results, files_dir):
    annotations = []
    for filename, ok, msg in results:
        if ok:
            continue
        repo_path_file = os.path.join(files_dir, filename + ".repo_path")
        repo_path = filename
        if os.path.isfile(repo_path_file):
            with open(repo_path_file) as f:
                repo_path = f.read().strip()
        annotations.append({
            "path": repo_path,
            "start_line": 1,
            "end_line": 1,
            "annotation_level": "failure",
            "title": f"PyKED: {filename}",
            "message": msg,
        })
    return annotations


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Run PyKED schema validation on a directory of ChemKED YAML files "
        "and post results back to a GitHub pull request as a check-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--files-dir",
            required=True,
            help="Directory containing decoded YAML files at their repo paths (and .repo_path sidecars).",
        )
        parser.add_argument(
            "--pr-repo",
            required=True,
            help="GitHub repo in owner/name format (e.g. LekiaAnonim/ChemKED-database).",
        )
        parser.add_argument(
            "--pr-number",
            type=int,
            required=True,
            help="Pull request number.",
        )
        parser.add_argument(
            "--commit-sha",
            required=True,
            help="Commit SHA for check-run attribution.",
        )
        parser.add_argument(
            "--github-token",
            default="",
            help="GitHub token override (defaults to GITHUB_TOKEN setting).",
        )

    def handle(self, *args, **options):
        files_dir = options["files_dir"]
        pr_repo = options["pr_repo"]
        pr_number = options["pr_number"]
        commit_sha = options["commit_sha"]
        github_token = (
            options["github_token"]
            or getattr(settings, "GITHUB_TOKEN", "")
            or os.getenv("GITHUB_TOKEN", "")
        )

        if not os.path.isdir(files_dir):
            raise CommandError(f"Directory not found: {files_dir}")

        if not github_token:
            raise CommandError(
                "GitHub token required. Set GITHUB_TOKEN env var or use --github-token."
            )

        yaml_files = sorted(
            f for f in
            glob.glob(os.path.join(files_dir, "**", "*.yaml"), recursive=True) +
            glob.glob(os.path.join(files_dir, "**", "*.yml"), recursive=True)
            if not f.endswith(".repo_path")
        )

        if not yaml_files:
            self.stdout.write(self.style.WARNING(f"No YAML files found in {files_dir}"))
            return

        check_run_id = _create_check_run(pr_repo, commit_sha, github_token, pr_number=pr_number)

        results = []
        any_failure = False
        for filepath in yaml_files:
            filename = os.path.relpath(filepath, files_dir)
            ok, msg = _validate_file(filepath)
            results.append((filename, ok, msg))
            if ok:
                self.stdout.write(self.style.SUCCESS(f"  [PASS] {filename} — {msg}"))
            else:
                any_failure = True
                self.stdout.write(self.style.ERROR(f"  [FAIL] {filename} — {msg}"))

        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        conclusion = "failure" if any_failure else "success"
        title = f"PyKED Validation — {passed}/{total} files passed"

        _update_check_run(
            pr_repo, check_run_id,
            conclusion=conclusion,
            title=title,
            summary=_build_summary(results),
            annotations=_build_annotations(results, files_dir),
            token=github_token,
        )

        self.stdout.write(self.style.SUCCESS(f"\nDone: {title}"))
