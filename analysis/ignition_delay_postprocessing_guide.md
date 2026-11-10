# Ignition Delay Post-Processing Guide

Post-processing pipeline for ignition-delay grid results.
Runs in two stages: **sanitize** (clean Cantera errors) → **merge** (combine shards + compute statistics).

---

## Prerequisites

```bash
cd kineticmodelssite
```

All commands below are Django management commands run via `python manage.py`.

---

## Directory Layout

A completed run directory looks like:

```
analysis/run_results/adversarial_idt/
  <run_label>/
    ignition_delay_task_0000_of_0200.csv   # shard CSVs (written by Slurm)
    ignition_delay_task_0000_of_0200.json   # shard metadata (written after CSV completes)
    ...
    _sanitized/                             # created by sanitize step
      ignition_delay_task_0000_of_0200.csv  # cleaned copies
      ...
    ignition_delay_merged.csv               # created by merge step
    ignition_delay_discrimination_map.csv   # per-condition statistics
    ignition_delay_merge_summary.json       # merge summary
```

---

## Step 1: Sanitize Shard CSVs

Collapses multi-line Cantera error tracebacks into single-line summaries.
Writes cleaned copies to a `_sanitized/` subdirectory — **originals are never modified**.

```bash
python manage.py sanitize_ignition_delay_shards \
    --run-label <run_label>
```

### Options

| Flag | Description |
|------|-------------|
| `--input-dir` | Base directory (default: `analysis/run_results/adversarial_idt`) |
| `--run-label` | **Required.** Subdirectory name of the run. |
| `--include-incomplete` | Also sanitize shards with no `.json` metadata (i.e., shards that didn't finish). |

### Example: archived run

Since the archived shards have no `.json` metadata files, use `--include-incomplete`:

```bash
python manage.py sanitize_ignition_delay_shards \
    --input-dir analysis/run_results/adversarial_idt/archive \
    --run-label ch4_full_grid_20260309_085023 \
    --include-incomplete
```

### What it does

- Reads each `ignition_delay_task_*.csv` in the run directory
- Skips shards without `.json` metadata (unless `--include-incomplete`)
- Skips shards whose `_sanitized/` copy is already up-to-date
- Writes sanitized copies to `<run_dir>/_sanitized/`

Multi-line errors like:

```
*******************************************************************************
CanteraError thrown by CVodesIntegrator::step:
CVodes error encountered. Error code: -4
At t = 0.000255665 and h = 8.13404e-11, the corrector convergence test failed...
```

Become:

```
CanteraError in CVodesIntegrator::step: CVodes error encountered. Error code: -4
```

---

## Step 2: Merge Shards + Compute Statistics

Combines all shard CSVs into a single merged file and computes per-condition
inter-mechanism discrimination statistics (mean, std, CV, success fraction).

```bash
python manage.py merge_ignition_delay_grid \
    --run-label <run_label>
```

### Options

| Flag | Description |
|------|-------------|
| `--input-dir` | Base directory (default: `analysis/run_results/adversarial_idt`) |
| `--run-label` | **Required.** Subdirectory name of the run. |
| `--allow-incomplete` | Proceed even if some shard metadata is missing. |
| `--overwrite` | Overwrite existing merged outputs. |

### Example: archived run

```bash
python manage.py merge_ignition_delay_grid \
    --input-dir analysis/run_results/adversarial_idt/archive \
    --run-label ch4_full_grid_20260309_085023 \
    --allow-incomplete
```

> `--allow-incomplete` is needed because the archived shards have no `.json` metadata.

### What it produces

| File | Description |
|------|-------------|
| `ignition_delay_merged.csv` | All shard rows concatenated. Prefers `_sanitized/` copies when available. |
| `ignition_delay_discrimination_map.csv` | Per-condition statistics: model counts, success fraction, mean/std/CV of ignition delay, min/max. |
| `ignition_delay_merge_summary.json` | Run metadata: row counts, condition counts, source shard list. |

### Discrimination map columns

| Column | Description |
|--------|-------------|
| `condition_index` | Grid condition index |
| `temperature_K` | Temperature in Kelvin |
| `pressure_atm` | Pressure in atm |
| `phi` | Equivalence ratio |
| `ignition_target` | Detection target (e.g., `temperature`, `OH`) |
| `ignition_type` | Detection method (e.g., `d/dt max`) |
| `model_count_total` | Number of models attempted |
| `model_count_success` | Models that produced a valid ignition delay |
| `model_count_failed` | Models that errored or produced no ignition |
| `success_fraction` | `success / total` |
| `mean_ignition_delay_s` | Mean delay across successful models |
| `std_ignition_delay_s` | Standard deviation |
| `cv_ignition_delay` | Coefficient of variation (`std / mean`) |
| `cv_percent` | CV as percentage |
| `min_ignition_delay_s` | Minimum delay |
| `max_ignition_delay_s` | Maximum delay |

---

## Full Pipeline Example (archived run)

```bash
cd kineticmodelssite

# 1. Sanitize
python manage.py sanitize_ignition_delay_shards \
    --input-dir analysis/run_results/adversarial_idt/archive \
    --run-label ch4_full_grid_20260309_085023 \
    --include-incomplete

# 2. Merge
python manage.py merge_ignition_delay_grid \
    --input-dir analysis/run_results/adversarial_idt/archive \
    --run-label ch4_full_grid_20260309_085023 \
    --allow-incomplete

# 3. Inspect outputs
head -5 analysis/run_results/adversarial_idt/archive/ch4_full_grid_20260309_085023/ignition_delay_discrimination_map.csv
cat analysis/run_results/adversarial_idt/archive/ch4_full_grid_20260309_085023/ignition_delay_merge_summary.json
```

---

## Notes

- **Safe during Slurm runs:** Sanitize writes to `_sanitized/`, never modifies originals. By default it skips in-progress shards (no `.json`).
- **Idempotent:** Both commands can be re-run. Use `--overwrite` on the merge step if outputs already exist.
- **Error handling:** Rows with errors are kept in the merged CSV but excluded from statistics. The `error` column is preserved; only multi-line tracebacks are collapsed.
