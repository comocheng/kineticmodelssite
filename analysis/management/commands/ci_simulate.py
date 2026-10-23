"""
Management command: run PyTeCK simulation for a ChemKED file and post
results back to a GitHub pull request.

Called by the ``pyteck-ci-simulate`` GitHub Actions workflow when a
``repository_dispatch`` event arrives from the ChemKED-database CI.

Usage::

    python manage.py ci_simulate \
        --chemked-yaml /tmp/methane_Smith_2020.yaml \
        --pr-repo LekiaAnonim/ChemKED-database \
        --pr-number 42 \
        --commit-sha abc123def456

Optional flags::

    --model-id 7          # explicit model PK (skip auto-detection)
    --max-models 3        # cap number of auto-detected models
"""

import json
import logging
import math
import os
import re
import tempfile

import requests
import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from analysis.models import (
    FuelModelCompatibility,
    FuelSpecies,
    SimulationRun,
    SimulationResult,
    SimulationStatus,
    TriggerType,
)
from analysis.services.simulation import (
    get_cantera_mechanism_from_model,
    parse_pyteck_results,
    run_pyteck_simulation,
)
from database.models import KineticModel

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Reuse the fuel detection heuristic from the PR service
_NON_FUEL = {
    "oxygen", "o2", "nitrogen", "n2", "argon", "ar", "helium", "he",
    "carbon dioxide", "co2", "water", "h2o", "neon", "ne", "krypton", "kr",
    "nitric oxide", "no", "nitrogen dioxide", "no2", "nitrous oxide", "n2o",
}


def _extract_fuel_from_yaml(filepath):
    """Parse a ChemKED YAML file and return the primary fuel species name."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None

    composition = None
    cp = data.get("common-properties", {})
    if isinstance(cp, dict) and "composition" in cp:
        composition = cp["composition"]
    if composition is None:
        dps = data.get("datapoints", [])
        if dps and isinstance(dps[0], dict) and "composition" in dps[0]:
            composition = dps[0]["composition"]
    if not composition or "species" not in composition:
        return None

    best_name, best_amount = None, -1
    for sp in composition["species"]:
        name = sp.get("species-name", "")
        amount_raw = sp.get("amount", [0])
        if isinstance(amount_raw, list):
            amount = float(amount_raw[0]) if amount_raw else 0
        else:
            amount = float(amount_raw)
        if name.lower() in _NON_FUEL:
            continue
        if amount > best_amount:
            best_amount = amount
            best_name = name
    return best_name


def _extract_fuel_smiles_from_yaml(filepath):
    """Parse a ChemKED YAML and return the primary fuel's SMILES & InChI."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None, None

    fuel_name = _extract_fuel_from_yaml(filepath)
    if not fuel_name:
        return None, None

    composition = None
    cp = data.get("common-properties", {})
    if isinstance(cp, dict) and "composition" in cp:
        composition = cp["composition"]
    if composition is None:
        dps = data.get("datapoints", [])
        if dps and isinstance(dps[0], dict) and "composition" in dps[0]:
            composition = dps[0]["composition"]
    if not composition or "species" not in composition:
        return None, None

    for sp in composition["species"]:
        if sp.get("species-name", "").lower() == fuel_name.lower():
            smiles = None
            inchi = sp.get("InChI", "")
            # Look for SMILES in the SMILES field
            smiles = sp.get("SMILES", "")
            return smiles or "", inchi or ""
    return None, None


def _formula_atom_count(formula, atom):
    """Return the count of *atom* (e.g. 'C', 'N') in a molecular formula string.

    Examples::

        _formula_atom_count('C4H9OH', 'C') -> 4
        _formula_atom_count('NH3',    'N') -> 1
        _formula_atom_count('H2',     'C') -> 0
    """
    if not formula:
        return 0
    m = re.search(rf'(?<![A-Z]){atom}(\d*)', formula)
    if not m:
        return 0
    return int(m.group(1)) if m.group(1) else 1


def _find_compatible_models(fuel_name, fuel_smiles, fuel_inchi, max_models=10):
    """Find kinetic models compatible with the given fuel species.

    Ranks compatible models by two scores:

    1. **Name score** — model_name contains one of the fuel's name variants.
    2. **Primary score** — the fuel is the largest molecule (by C count, or N
       count for nitrogen-only fuels) among all species compatible with that
       model.  This is the "largest molecule" heuristic: mechanisms are built
       hierarchically, so the target fuel is always the heaviest species.

    Falls back to alphabetical model name when scores are equal.
    """
    models_found = []

    # Try InChI match on FuelSpecies first (most reliable)
    fuel_qs = FuelSpecies.objects.none()
    if fuel_inchi:
        fuel_qs = FuelSpecies.objects.filter(inchi=fuel_inchi)
    if not fuel_qs.exists() and fuel_smiles:
        fuel_qs = FuelSpecies.objects.filter(smiles=fuel_smiles)
    if not fuel_qs.exists() and fuel_name:
        fuel_qs = FuelSpecies.objects.filter(
            common_name__iexact=fuel_name
        ) | FuelSpecies.objects.filter(
            name_variants__contains=[fuel_name]
        )

    for fuel_obj in fuel_qs[:1]:
        fuel_carbons = _formula_atom_count(fuel_obj.formula or '', 'C')
        fuel_nitrogens = _formula_atom_count(fuel_obj.formula or '', 'N')

        # All models with this fuel present
        compat_rows = list(
            FuelModelCompatibility.objects
            .filter(fuel=fuel_obj, is_compatible=True)
            .select_related("kinetic_model")
        )
        if not compat_rows:
            break

        # Batch query: for every compatible model get the max C and N count
        # across ALL its compatible fuels — used to detect whether this fuel
        # is the primary (heaviest) species in the mechanism.
        model_pks = [c.kinetic_model_id for c in compat_rows]
        model_max_c = {}
        model_max_n = {}
        for row in (
            FuelModelCompatibility.objects
            .filter(kinetic_model_id__in=model_pks, is_compatible=True)
            .values('kinetic_model_id', 'fuel__formula')
        ):
            mid = row['kinetic_model_id']
            f = row['fuel__formula'] or ''
            c = _formula_atom_count(f, 'C')
            n = _formula_atom_count(f, 'N')
            if c > model_max_c.get(mid, 0):
                model_max_c[mid] = c
            if n > model_max_n.get(mid, 0):
                model_max_n[mid] = n

        fuel_names_lower = {
            v.lower() for v in ([fuel_name or ''] + list(fuel_obj.name_variants or []))
            if v
        }

        scored = []
        for compat in compat_rows:
            mid = compat.kinetic_model_id
            mname = compat.kinetic_model.model_name

            # Score 1: model name contains a fuel name variant
            name_score = int(any(fn in mname.lower() for fn in fuel_names_lower))

            # Score 2: fuel is the heaviest compatible species in this model
            max_c = model_max_c.get(mid, 0)
            max_n = model_max_n.get(mid, 0)
            if fuel_carbons == 0 and fuel_nitrogens == 0:
                # H2-like: primary only for mechanisms with no carbon species
                primary_score = int(max_c == 0)
            elif fuel_carbons == 0:
                # Nitrogen-only fuel (e.g. NH3): primary if it has the most N
                primary_score = int(fuel_nitrogens >= max_n)
            else:
                # Carbon-containing fuel: primary if it has the most carbons
                primary_score = int(fuel_carbons >= max_c)

            scored.append((name_score, primary_score, mname, compat.kinetic_model))

        # Sort: name match → primary fuel match → alphabetical
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        models_found = [model for _, _, _, model in scored[:max_models]]

    return models_found


def _get_experiment_type(filepath):
    """Return the experiment-type from a ChemKED file."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    return data.get("experiment-type", "").lower().strip()


_GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _gh_headers(token):
    return {**_GH_HEADERS, "Authorization": f"token {token}"}


def _post_github_comment(pr_repo, pr_number, body, token):
    """Post a comment on a GitHub PR."""
    url = f"{GITHUB_API}/repos/{pr_repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=_gh_headers(token), json={"body": body}, timeout=30)
    if resp.status_code not in (200, 201):
        logger.error("Failed to post PR comment: %s %s", resp.status_code, resp.text)
    return resp


def _create_check_run(pr_repo, head_sha, token, pr_number=None):
    """Create an in-progress check-run and return its ID."""
    url = f"{GITHUB_API}/repos/{pr_repo}/check-runs"
    details_url = (
        f"https://github.com/{pr_repo}/pull/{pr_number}"
        if pr_number else f"https://github.com/{pr_repo}"
    )
    resp = requests.post(
        url,
        headers=_gh_headers(token),
        json={
            "name": "PyTeCK Simulation",
            "head_sha": head_sha,
            "status": "in_progress",
            "started_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details_url": details_url,
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        logger.error("Failed to create check-run: %s %s", resp.status_code, resp.text)
        return None
    check_run_id = resp.json().get("id")
    logger.info("Created check-run #%s", check_run_id)
    return check_run_id


def _update_check_run(pr_repo, check_run_id, conclusion, title, summary, annotations, token):
    """Mark a check-run as completed with results."""
    if check_run_id is None:
        return
    url = f"{GITHUB_API}/repos/{pr_repo}/check-runs/{check_run_id}"
    resp = requests.patch(
        url,
        headers=_gh_headers(token),
        json={
            "status": "completed",
            "conclusion": conclusion,  # "success", "failure", "neutral"
            "completed_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "output": {
                "title": title,
                "summary": summary,
                # GitHub caps annotations at 50 per request
                "annotations": annotations[:50],
            },
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        logger.error("Failed to update check-run: %s %s", resp.status_code, resp.text)


def _build_annotations(results_table, repo_file_path):
    """Convert simulation results into GitHub check-run annotations.

    Each failed model becomes a ``failure`` annotation; passed models become
    ``notice`` annotations.  ``repo_file_path`` is the repo-relative path of
    the contributed YAML file used for annotation linking.
    """
    annotations = []
    for r in results_table:
        level = "failure" if not r["success"] else "notice"
        if r["success"]:
            ef_str = f'{r["error_function"]:.4f}' if r["error_function"] is not None else "N/A"
            msg = f'{r["model_name"]}: PASS — error function {ef_str}, {r["num_datapoints"]} datapoints'
        else:
            msg = f'{r["model_name"]}: FAIL — {r["message"]}'
        annotations.append({
            "path": repo_file_path,
            "start_line": 1,
            "end_line": 1,
            "annotation_level": level,
            "title": f'PyTeCK: {r["model_name"]}',
            "message": msg,
        })
    return annotations


class Command(BaseCommand):
    help = (
        "Run PyTeCK simulation for a ChemKED YAML file and post "
        "results back to a GitHub pull request."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--chemked-yaml",
            required=True,
            help="Path to the ChemKED YAML file to simulate.",
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
            help="Commit SHA to set status on.",
        )
        parser.add_argument(
            "--model-id",
            type=int,
            help="Explicit kinetic model PK (skip auto-detection).",
        )
        parser.add_argument(
            "--max-models",
            type=int,
            default=10,
            help="Max number of auto-detected models to simulate against.",
        )
        parser.add_argument(
            "--github-token",
            default="",
            help="GitHub token override (defaults to GITHUB_TOKEN setting).",
        )
        parser.add_argument(
            "--repo-file-path",
            default="",
            help=(
                "Repo-relative path of the contributed YAML file "
                "(e.g. methane/Smith_2020/x12345678.yaml). "
                "Used to link check-run annotations to the file in the PR diff."
            ),
        )

    def handle(self, *args, **options):
        chemked_path = options["chemked_yaml"]
        pr_repo = options["pr_repo"]
        pr_number = options["pr_number"]
        commit_sha = options["commit_sha"]
        model_id = options.get("model_id")
        max_models = options["max_models"]
        repo_file_path = options.get("repo_file_path") or os.path.basename(chemked_path)
        github_token = options["github_token"] or getattr(settings, "GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")

        if not os.path.isfile(chemked_path):
            raise CommandError(f"File not found: {chemked_path}")

        if not github_token:
            raise CommandError(
                "GitHub token required. Set GITHUB_TOKEN env var or use --github-token."
            )

        # Create in-progress check-run (visible on GitHub and polled by the web UI)
        check_run_id = _create_check_run(pr_repo, commit_sha, github_token, pr_number=pr_number)

        filename = os.path.basename(chemked_path)
        self.stdout.write(self.style.NOTICE(f"Processing: {filename}"))

        # Check experiment type
        exp_type = _get_experiment_type(chemked_path)
        if exp_type != "ignition delay":
            msg = f"Skipped — experiment type '{exp_type}' is not supported by PyTeCK"
            self.stdout.write(self.style.WARNING(msg))
            _update_check_run(
                pr_repo, check_run_id,
                conclusion="neutral",
                title=f"PyTeCK Simulation — skipped ({exp_type})",
                summary=f"⏭️ {msg}\n\nOnly ignition delay datasets can be simulated.",
                annotations=[],
                token=github_token,
            )
            _post_github_comment(
                pr_repo, pr_number,
                f"### PyTeCK Simulation\n\n⏭️ {msg}\n\n"
                f"Only ignition delay datasets can be simulated.",
                github_token,
            )
            return

        # Find compatible models
        if model_id:
            try:
                models_to_test = [KineticModel.objects.get(pk=model_id)]
            except KineticModel.DoesNotExist:
                raise CommandError(f"KineticModel with pk={model_id} not found.")
            self.stdout.write(f"  Using explicit model: {models_to_test[0].model_name}")
        else:
            fuel_name = _extract_fuel_from_yaml(chemked_path)
            fuel_smiles, fuel_inchi = _extract_fuel_smiles_from_yaml(chemked_path)
            self.stdout.write(
                f"  Fuel: {fuel_name} | SMILES: {fuel_smiles} | InChI: {fuel_inchi}"
            )
            models_to_test = _find_compatible_models(
                fuel_name, fuel_smiles, fuel_inchi, max_models
            )
            if not models_to_test:
                msg = f"No compatible kinetic models found for fuel '{fuel_name}'"
                self.stdout.write(self.style.WARNING(msg))
                _update_check_run(
                    pr_repo, check_run_id,
                    conclusion="neutral",
                    title="PyTeCK Simulation — no compatible models",
                    summary=(
                        f"⚠️ {msg}\n\n"
                        f"No models in the database contain the fuel species "
                        f"**{fuel_name}** (InChI: `{fuel_inchi}`).\n"
                        f"The dataset is valid and can still be merged."
                    ),
                    annotations=[],
                    token=github_token,
                )
                _post_github_comment(
                    pr_repo, pr_number,
                    f"### PyTeCK Simulation\n\n⚠️ {msg}\n\n"
                    f"No models in the database contain the fuel species "
                    f"**{fuel_name}** (InChI: `{fuel_inchi}`).\n"
                    f"The dataset is valid and can still be merged.",
                    github_token,
                )
                return
            self.stdout.write(
                f"  Found {len(models_to_test)} compatible model(s): "
                + ", ".join(m.model_name for m in models_to_test)
            )

        # We need a temporary ExperimentDataset-like object for the simulation.
        # The CI simulation works with the ChemKED file directly on disk,
        # so we create a lightweight wrapper.
        from chemked_database.models import ExperimentDataset
        temp_dataset = _create_temp_dataset(chemked_path)

        # Run simulations
        results_table = []
        any_failure = False

        for model in models_to_test:
            self.stdout.write(f"  Simulating: {model.model_name}...")
            results_dir = tempfile.mkdtemp(prefix="pyteck_ci_")

            try:
                success, message, results_dict = run_pyteck_simulation(
                    model=model,
                    dataset=temp_dataset,
                    results_dir=results_dir,
                    skip_validation=True,
                )

                # Create SimulationRun record
                run = SimulationRun.objects.create(
                    kinetic_model=model,
                    dataset=temp_dataset,
                    status=SimulationStatus.COMPLETED if success else SimulationStatus.FAILED,
                    triggered_by=TriggerType.API,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    results_dir=results_dir,
                    error_message="" if success else message,
                )

                error_func = None
                num_datapoints = 0
                if success and results_dict:
                    parsed = parse_pyteck_results(results_dict)
                    error_func = parsed.get("average_error_function")
                    dev_func = parsed.get("average_deviation_function")

                    # Guard: PyTeCK returns -Infinity when τ_sim → 0 (model out of range).
                    # PostgreSQL JSON rejects non-finite floats, so catch this before
                    # hitting the DB and surface a clear failure message instead.
                    non_finite = (
                        (error_func is not None and not math.isfinite(error_func))
                        or (dev_func is not None and not math.isfinite(dev_func))
                    )
                    if non_finite:
                        success = False
                        message = (
                            "Simulation produced a non-finite result "
                            f"(error={error_func}, deviation={dev_func}). "
                            "The model is likely outside its valid range for these conditions "
                            "(e.g. predicted instantaneous or no ignition)."
                        )
                        run.status = SimulationStatus.FAILED
                        run.error_message = message
                        run.save(update_fields=["status", "error_message"])
                    else:
                        for ds in parsed.get("datasets", []):
                            num_datapoints += len(ds.get("datapoints", []))

                        SimulationResult.objects.create(
                            simulation_run=run,
                            average_error_function=error_func,
                            average_deviation_function=dev_func,
                            results_json=results_dict,
                            num_datapoints=num_datapoints,
                            num_successful=num_datapoints,
                        )
                        run.spec_keys_snapshot = results_dict.get("spec_keys", {})
                        run.save(update_fields=["spec_keys_snapshot"])

                results_table.append({
                    "model_name": model.model_name,
                    "model_pk": model.pk,
                    "success": success,
                    "message": message,
                    "error_function": error_func,
                    "num_datapoints": num_datapoints,
                })

                if success:
                    ef_str = f"{error_func:.4f}" if error_func is not None else "N/A"
                    self.stdout.write(
                        self.style.SUCCESS(f"    ✓ {model.model_name}: E={ef_str}, {num_datapoints} pts")
                    )
                else:
                    any_failure = True
                    self.stdout.write(self.style.ERROR(f"    ✗ {model.model_name}: {message}"))

            except Exception as e:
                logger.exception(f"Unexpected error simulating {model.model_name}")
                any_failure = True
                results_table.append({
                    "model_name": model.model_name,
                    "model_pk": model.pk,
                    "success": False,
                    "message": str(e),
                    "error_function": None,
                    "num_datapoints": 0,
                })

        # Remove the temp ExperimentDataset stub — real records are created by
        # sync_chemked only after the PR is merged. SimulationRun rows survive
        # because dataset is SET_NULL on delete.
        if temp_dataset and temp_dataset.pk:
            temp_dataset.delete()

        # Build markdown comment and check-run output
        comment_body = _build_comment(filename, results_table)

        passed = sum(1 for r in results_table if r["success"])
        total = len(results_table)
        conclusion = "success" if not any_failure else "failure"
        title = f"PyTeCK Simulation — {passed}/{total} models passed"

        # Update check-run to completed (visible on GitHub and on the web UI via polling)
        annotations = _build_annotations(results_table, repo_file_path)
        _update_check_run(
            pr_repo, check_run_id,
            conclusion=conclusion,
            title=title,
            summary=comment_body,
            annotations=annotations,
            token=github_token,
        )

        # Also post the markdown table as a PR comment for convenience
        _post_github_comment(pr_repo, pr_number, comment_body, github_token)

        self.stdout.write(self.style.SUCCESS(f"\nDone: {title}"))


def _create_temp_dataset(chemked_path):
    """Create (or reuse) an ExperimentDataset record for the CI file.

    The dataset is saved to the DB so that ``run_pyteck_simulation()``
    can load it via ``get_chemked_dataset_path()``.
    """
    from chemked_database.models import ExperimentDataset

    with open(chemked_path, "r") as f:
        data = yaml.safe_load(f)

    exp_type = data.get("experiment-type", "ignition delay")
    abs_path = os.path.abspath(chemked_path)

    dataset, _ = ExperimentDataset.objects.get_or_create(
        chemked_file_path=abs_path,
        defaults={"experiment_type": exp_type},
    )
    return dataset


def _build_comment(filename, results_table):
    """Build a GitHub PR comment in markdown."""
    lines = [
        "### PyTeCK Simulation Results",
        "",
        f"**File:** `{filename}`",
        "",
        "| Model | Status | Error Function | Datapoints |",
        "|-------|--------|---------------|------------|",
    ]

    for r in results_table:
        status = "✅ Pass" if r["success"] else "❌ Fail"
        ef = f'{r["error_function"]:.4f}' if r["error_function"] is not None else "—"
        pts = r["num_datapoints"] or "—"
        lines.append(f'| {r["model_name"]} | {status} | {ef} | {pts} |')

    if not results_table:
        lines.append("| — | No models tested | — | — |")

    lines.append("")

    # Add failure details
    failures = [r for r in results_table if not r["success"]]
    if failures:
        lines.append("<details><summary>Failure details</summary>\n")
        for r in failures:
            lines.append(f"**{r['model_name']}:** {r['message']}\n")
        lines.append("</details>\n")

    lines.append(
        "*Simulated on [kineticmodelssite](https://github.com/"
        f"{os.getenv('GITHUB_REPO_OWNER', 'LekiaAnonim')}/kineticmodelssite) "
        f"using auto-detected compatible models.*"
    )

    return "\n".join(lines)
