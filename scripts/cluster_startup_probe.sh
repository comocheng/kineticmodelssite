#!/usr/bin/env bash
# Measure real SLURM start-up latency: submit -> RUNNING, for N tiny jobs.
# Prints CSV: index,submit_to_running_seconds
set -u
N="${1:-10}"
PARTITION="${2:-west}"
echo "index,startup_seconds"
for i in $(seq 1 "$N"); do
  t0=$(date +%s.%N)
  jid=$(sbatch --parsable --partition="$PARTITION" --job-name="bench$i" \
        --time=00:02:00 --mem=512M --wrap='sleep 5' 2>/dev/null)
  if [ -z "$jid" ]; then echo "$i,NA"; continue; fi
  # Poll state until it leaves PENDING (RUNNING, or already gone/completed).
  while true; do
    st=$(squeue -j "$jid" -h -o %T 2>/dev/null)
    if [ -z "$st" ] || [ "$st" = "RUNNING" ] || [ "$st" = "COMPLETING" ] || [ "$st" = "COMPLETED" ]; then
      break
    fi
    sleep 0.2
  done
  t1=$(date +%s.%N)
  dt=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
  echo "$i,$dt"
  # Clean up: cancel if somehow still around.
  scancel "$jid" >/dev/null 2>&1 || true
done
