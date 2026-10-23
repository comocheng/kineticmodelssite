#!/bin/bash
#SBATCH --job-name=idt-grid-ch4
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=24:00:00
#SBATCH --array=0-199
#SBATCH --output=analysis/run_logs/slurm/%x-%A_%a.out
#SBATCH --error=analysis/run_logs/slurm/%x-%A_%a.err

set -euo pipefail

PROJECT_ROOT="/path/to/Prometheus/kineticmodelssite"
CONDA_SH="/path/to/miniconda3/etc/profile.d/conda.sh"
CONDA_ENV="kms"
RUN_LABEL="ch4_full_grid_$(date +%Y%m%d_%H%M%S)"
TASK_COUNT=200

source "$CONDA_SH"
conda activate "$CONDA_ENV"

cd "$PROJECT_ROOT"
mkdir -p analysis/run_logs/slurm

python manage.py run_ignition_delay_grid \
  --use-slurm-env \
  --task-count "$TASK_COUNT" \
  --run-label "$RUN_LABEL" \
  --fuel-smiles C \
  --output-dir analysis/run_results/adversarial_idt \
  --ignition-target temperature \
  --ignition-type 'd/dt max' \
  --max-time 0.05 \
  --max-steps 5000
