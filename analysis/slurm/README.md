# Ignition Delay Grid on Slurm

Use the management command below as the batch entry point rather than executing the notebook on the cluster.

## Local smoke test

From [manage.py](../../manage.py):

```bash
python manage.py run_ignition_delay_grid \
  --run-label smoke_test \
  --fuel-smiles C \
  --temperatures 1200,1400 \
  --pressures-atm 1,10 \
  --phis 0.5,1.0 \
  --limit-models 2 \
  --limit-conditions 4 \
  --ignition-target temperature \
  --ignition-type 'd/dt max' \
  --max-time 0.05 \
  --overwrite
```

This writes one CSV shard and one JSON metadata file under:

```text
analysis/run_results/adversarial_idt/smoke_test/
```

## Full Slurm array run

1. Edit [run_ignition_delay_grid.slurm](run_ignition_delay_grid.slurm) and set:
   - `PROJECT_ROOT`
   - `CONDA_SH`
   - `CONDA_ENV`
   - `TASK_COUNT`
2. Submit the array job:

```bash
sbatch analysis/slurm/run_ignition_delay_grid.slurm
```

Each Slurm task runs one shard of the full notebook grid and writes:

```text
analysis/run_results/adversarial_idt/<run_label>/ignition_delay_task_XXXX_of_YYYY.csv
analysis/run_results/adversarial_idt/<run_label>/ignition_delay_task_XXXX_of_YYYY.json
```

## How sharding works

- The full T-P-phi grid is enumerated once logically.
- A shard processes conditions where `condition_index % task_count == task_index`.
- Every selected mechanism is evaluated for each condition in that shard.
- This means you can change `TASK_COUNT` without changing the underlying grid definition.

## Notes

- If you want to target specific mechanisms, add `--model-pks 12 15 18`.
- If your cluster does not provide `SLURM_ARRAY_TASK_COUNT`, the template already passes `--task-count` explicitly.
- Re-running the same shard requires `--overwrite`, otherwise the command stops to avoid clobbering outputs.

## Merge and compute discrimination map

After the array job finishes, merge all shard CSVs and compute the per-condition inter-mechanism coefficient of variation:

```bash
python manage.py merge_ignition_delay_grid \
  --run-label <run_label> \
  --overwrite
```

This creates:

```text
analysis/run_results/adversarial_idt/<run_label>/ignition_delay_merged.csv
analysis/run_results/adversarial_idt/<run_label>/ignition_delay_discrimination_map.csv
analysis/run_results/adversarial_idt/<run_label>/ignition_delay_merge_summary.json
```

The discrimination CSV contains one row per T-P-phi condition and PyTeCK ignition-setting pair with model counts, success fraction, mean ignition delay, standard deviation, and `cv_ignition_delay` / `cv_percent`.