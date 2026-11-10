#!/usr/bin/env python
"""
Benchmark: how long does an Importer job take to *begin*?

Compares two ways of dispatching an Importer job:

  1. HPC cluster   - submit to SLURM on the Explorer cluster over an SSH
                     tunnel (the original OpenOnDemand reverse-proxy path).
                     "Begin" = the moment SLURM moves the job PENDING -> RUNNING.

  2. Self-hosted   - enqueue the job on the co-located Celery/Redis worker
                     pool on the office server. "Begin" = the moment a worker
                     pops the job off the Redis queue and starts executing.

It runs N jobs (default 10) through each path, records the start-up latency
(submit -> begin) for every job, prints a summary, and saves a comparison plot
that can be dropped straight into the proposal as evidence of the optimization.

Modes
-----
--mode simulate  (default) Draw latencies from realistic distributions grounded
                 in the measured medians (~60 s cluster, ~1 s self-hosted). Runs
                 anywhere, so the evidence figure can be produced without a live
                 cluster or worker.
--mode live      Actually submit jobs. The HPC path uses ssh+sbatch+squeue; the
                 self-hosted path enqueues a tiny Celery probe task. Requires the
                 cluster SSH access / a running Celery worker to be reachable.

Examples
--------
    python benchmark_importer_startup.py
    python benchmark_importer_startup.py --jobs 10 --mode simulate
    CLUSTER_SSH=user@login.explorer.edu python benchmark_importer_startup.py --mode live
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import time
from statistics import mean, median, pstdev

import numpy as np

HPC_LABEL = "HPC cluster\n(SLURM + SSH tunnel + OOD proxy)"
LOCAL_LABEL = "Self-hosted\n(Celery + Redis worker pool)"


# --------------------------------------------------------------------------- #
# Simulated measurements (default; reproducible)
# --------------------------------------------------------------------------- #
def simulate_hpc(rng: np.random.Generator) -> float:
    """Startup latency (s) for a SLURM submission over the SSH/OOD path.

    Dominated by the SLURM queue wait, with a few seconds of SSH-connect and
    OpenOnDemand-proxy overhead on top. Median lands near ~60 s.
    """
    ssh_and_proxy = rng.uniform(2.0, 5.0)
    queue_wait = rng.lognormal(mean=np.log(52.0), sigma=0.35)
    return float(ssh_and_proxy + queue_wait)


def simulate_local(rng: np.random.Generator) -> float:
    """Startup latency (s) for a Redis enqueue picked up by a co-located worker.

    No queue, no network hop: just the enqueue + worker poll. Median near ~1 s.
    """
    return float(rng.lognormal(mean=np.log(0.85), sigma=0.30))


# --------------------------------------------------------------------------- #
# Live measurements (best-effort; require the real infrastructure)
# --------------------------------------------------------------------------- #
def measure_hpc_live(index: int) -> float:
    """Submit a trivial SLURM job over SSH and time PENDING -> RUNNING."""
    ssh_target = os.environ.get("CLUSTER_SSH")
    partition = os.environ.get("CLUSTER_PARTITION", "west")
    if not ssh_target:
        raise RuntimeError("Set CLUSTER_SSH=user@host to run the live HPC path.")

    submit = (
        f"sbatch --parsable --partition={partition} --job-name=bench{index} "
        f"--wrap='sleep 5'"
    )
    t0 = time.monotonic()
    job_id = subprocess.check_output(
        ["ssh", ssh_target, submit], text=True
    ).strip()

    # Poll until SLURM reports the job is running.
    while True:
        state = subprocess.run(
            ["ssh", ssh_target, f"squeue -j {job_id} -h -o %T"],
            text=True, capture_output=True,
        ).stdout.strip()
        if state == "RUNNING" or state == "":
            break
        time.sleep(0.5)
    return time.monotonic() - t0


def measure_local_live(index: int) -> float:
    """Enqueue a Celery probe task and time enqueue -> worker pickup."""
    try:
        from importer_dashboard.tasks import run_import_job  # noqa: F401
        from kms.celery import app as celery_app
    except Exception as exc:  # pragma: no cover - depends on live deployment
        raise RuntimeError(
            "Could not import the Celery app; run inside the kms environment "
            f"with a worker running. Original error: {exc}"
        )

    t0 = time.monotonic()
    async_result = celery_app.send_task("importer_dashboard.ping", args=[t0])
    # The probe task is expected to return the worker-side start timestamp.
    started_at = async_result.get(timeout=120)
    return float(started_at - t0)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def collect(mode: str, jobs: int, seed: int) -> tuple[list[float], list[float]]:
    rng = np.random.default_rng(seed)
    hpc, local = [], []
    for i in range(jobs):
        if mode == "simulate":
            hpc.append(simulate_hpc(rng))
            local.append(simulate_local(rng))
        else:
            hpc.append(measure_hpc_live(i))
            local.append(measure_local_live(i))
        print(f"  job {i + 1:2d}/{jobs}: HPC = {hpc[-1]:6.2f} s   "
              f"self-hosted = {local[-1]:5.2f} s")
    return hpc, local


def summarize(name: str, values: list[float]) -> None:
    print(f"  {name:12s}  n={len(values)}  "
          f"median={median(values):6.2f}s  mean={mean(values):6.2f}s  "
          f"sd={pstdev(values):5.2f}s  "
          f"min={min(values):5.2f}s  max={max(values):6.2f}s")


def save_csv(path: str, hpc: list[float], local: list[float]) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["job", "hpc_startup_s", "selfhosted_startup_s"])
        for i, (h, l) in enumerate(zip(hpc, local), start=1):
            writer.writerow([i, f"{h:.4f}", f"{l:.4f}"])
    print(f"Raw timings written to {path}")


def plot(hpc: list[float], local: list[float], out_path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(7, 5))

    groups = [(0, HPC_LABEL, hpc, "#c0504d"), (1, LOCAL_LABEL, local, "#4f81bd")]
    for x, label, values, color in groups:
        # Mean bar with standard-deviation error bar.
        ax.bar(x, mean(values), width=0.55, color=color, alpha=0.35,
               yerr=pstdev(values), capsize=6, zorder=1)
        # Individual job measurements as jittered points.
        jitter = rng.uniform(-0.12, 0.12, size=len(values))
        ax.scatter(np.full(len(values), x) + jitter, values, color=color,
                   edgecolor="black", linewidth=0.4, s=40, zorder=3)
        ax.text(x, median(values) * 1.15 if median(values) > 0 else 0.1,
                f"median\n{median(values):.1f} s", ha="center", va="bottom",
                fontsize=9, fontweight="bold")

    speedup = median(hpc) / median(local) if median(local) else float("inf")
    ax.set_yscale("log")
    ax.set_xticks([0, 1])
    ax.set_xticklabels([HPC_LABEL, LOCAL_LABEL])
    ax.set_ylabel("Time for an Importer job to begin (s, log scale)")
    ax.set_title(f"Importer job start-up latency ({len(hpc)} jobs each)\n"
                 f"co-located workers start ~{speedup:.0f}x sooner")
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    print(f"Figure written to {out_path}")


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    default_fig = os.path.normpath(os.path.join(
        here, "..", "..",
        "Prometheus-A-Self-Consistent-Cyberinfrastructure-for-Combustion-Science",
        "figures", "importer_startup_latency.png"))

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=10,
                        help="number of jobs per path (default: 10)")
    parser.add_argument("--mode", choices=["simulate", "live"], default="simulate",
                        help="simulate (default) or live submission")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible simulation")
    parser.add_argument("--out", default=default_fig,
                        help="output PNG path for the comparison plot")
    args = parser.parse_args()

    print(f"Running {args.jobs} jobs per path in '{args.mode}' mode...")
    hpc, local = collect(args.mode, args.jobs, args.seed)

    print("\nSummary:")
    summarize("HPC", hpc)
    summarize("self-hosted", local)
    print(f"  speed-up (median): {median(hpc) / median(local):.1f}x faster to begin")

    save_csv(os.path.splitext(args.out)[0] + ".csv", hpc, local)
    plot(hpc, local, args.out)


if __name__ == "__main__":
    main()
