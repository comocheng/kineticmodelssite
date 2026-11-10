#!/bin/bash
#SBATCH --job-name=idt-grid-ch4-OH
#SBATCH --partition=west
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=96:00:00
#SBATCH --array=0-199
#SBATCH --nodelist=c3047
#SBATCH --output=analysis/run_logs/slurm/OH/%x-%A_%a.out
#SBATCH --error=analysis/run_logs/slurm/OH/%x-%A_%a.err

set -euo pipefail

PROJECT_ROOT="/projects/westgroup/lekia.p/kineticmodelssite"
CONDA_SH="/projects/westgroup/lekia.p/miniforge3/etc/profile.d/conda.sh"
CONDA_ENV="kms"
RUN_LABEL="ch4_full_OH_grid_$(date +%Y%m%d_%H%M%S)"
TASK_COUNT=200

source "$CONDA_SH"
conda activate "$CONDA_ENV"

export DB_HOST="c3047"

cd "$PROJECT_ROOT"
mkdir -p analysis/run_logs/slurm/OH

python manage.py run_ignition_delay_grid \
  --use-slurm-env \
  --task-count "$TASK_COUNT" \
  --run-label "$RUN_LABEL" \
  --fuel-smiles C \
  --output-dir analysis/run_results/adversarial_idt/OH \
  --ignition-target OH \
  --ignition-type 'd/dt max' \
  --max-time 10 \
  --max-steps 5000
