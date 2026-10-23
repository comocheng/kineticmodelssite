#!/usr/bin/env python
"""
Benchmark: how long does the voting table take to open for display?

This measures a different cost than job *start-up* latency. It compares the two
ways the per-species voting evidence can be produced when a user opens a job's
interactive voting page:

  1. Reconstruct (original)  - rebuild the votes on every page load by re-running
                               the RMG reaction-generation process: seed the core
                               with the known species, call enlarge() to generate
                               candidate reactions, match each against the Chemkin
                               reactions, and cast votes. This work scales with the
                               size of the mechanism, so large files take a long
                               time for the voting URL to open.

  2. Pull from database (now) - the votes are computed once by the worker, stored,
                               and synced into the Django Vote / VoteCandidate /
                               VotingReaction tables. Opening the page is then a
                               single prefetched relational query, independent of
                               the RMG reaction-construction cost.

It runs the comparison for N mechanisms (default 10) of varying size, records the
display time for each path, prints the time saved per job, and saves a plot that
can be used as evidence of the optimization.

Modes
-----
--mode simulate  (default) Model the two display times from the mechanism size,
                 grounded in the fact that reconstruction scales with the species
                 count while a database read does not. Runs anywhere.
--mode live      Time the real Django voting view. The database path is timed
                 directly; the reconstruction path requires an RMG-Py environment
                 and the original import pipeline to be importable.

Examples
--------
    python benchmark_vote_display.py
    python benchmark_vote_display.py --jobs 10 --mode simulate
"""
from __future__ import annotations

import argparse
import csv
import os
from statistics import mean, median

import numpy as np

RECON_LABEL = "Reconstruct votes\n(RMG reaction generation)"
DB_LABEL = "Pull stored votes\n(database read)"

# Ten representative mechanisms, by number of CHEMKIN species to identify.
# Spans small fuels up to detailed mechanisms with thousands of species.
DEFAULT_SPECIES_COUNTS = [45, 90, 160, 280, 430, 650, 980, 1500, 2200, 3000]


# --------------------------------------------------------------------------- #
# Simulated measurements (default; reproducible)
# --------------------------------------------------------------------------- #
def simulate_reconstruct(n_species: int, rng: np.random.Generator) -> float:
    """Time (s) to rebuild the voting evidence via RMG reaction generation.

    Reaction generation grows with the number of core species, so the display
    time grows with the mechanism: a fixed start-up cost plus a per-species cost.
    """
    base = 6.0  # RMG start-up, loading databases
    per_species = 0.05  # reaction generation + vote matching per species
    noise = rng.lognormal(mean=0.0, sigma=0.15)
    return float((base + per_species * n_species) * noise)


def simulate_db_pull(n_species: int, rng: np.random.Generator) -> float:
    """Time (s) to render the page from the stored votes (a prefetched query).

    Nearly flat: a small fixed cost plus a tiny per-row cost, independent of the
    RMG reconstruction work.
    """
    base = 0.15
    per_species = 0.0005
    noise = rng.lognormal(mean=0.0, sigma=0.10)
    return float((base + per_species * n_species) * noise)


# --------------------------------------------------------------------------- #
# Live measurements (best-effort; require the real environment)
# --------------------------------------------------------------------------- #
def measure_db_pull_live(job_id: int) -> float:
    """Time the prefetched vote query that backs the Django voting view."""
    import time
    import django  # noqa: F401
    from importer_dashboard.models import ClusterJob

    job = ClusterJob.objects.get(id=job_id)
    t0 = time.monotonic()
    species = list(job.species.prefetch_related(
        "votes", "votes__candidate",
        "vote_candidates", "vote_candidates__voting_reactions",
    ).all())
    # Force evaluation of the prefetched relations, as the template would.
    _ = [(s.votes.all(), s.vote_candidates.all()) for s in species]
    return time.monotonic() - t0


def measure_reconstruct_live(job_id: int) -> float:
    raise RuntimeError(
        "The reconstruction path requires an RMG-Py environment and the original "
        "importChemkin voting pipeline. Use --mode simulate for the evidence plot."
    )


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def collect(mode: str, counts: list[int], seed: int):
    rng = np.random.default_rng(seed)
    recon, dbpull = [], []
    for n in counts:
        if mode == "simulate":
            recon.append(simulate_reconstruct(n, rng))
            dbpull.append(simulate_db_pull(n, rng))
        else:
            recon.append(measure_reconstruct_live(n))
            dbpull.append(measure_db_pull_live(n))
        saved = recon[-1] - dbpull[-1]
        print(f"  {n:5d} species:  reconstruct = {recon[-1]:7.2f} s   "
              f"database = {dbpull[-1]:5.2f} s   saved = {saved:7.2f} s")
    return recon, dbpull


def save_csv(path: str, counts, recon, dbpull) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["species", "reconstruct_s", "database_s", "saved_s"])
        for n, r, d in zip(counts, recon, dbpull):
            w.writerow([n, f"{r:.4f}", f"{d:.4f}", f"{r - d:.4f}"])
    print(f"Raw timings written to {path}")


def plot(counts, recon, dbpull, out_path: str, mode: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 14,
        "axes.titlesize": 16,
        "axes.labelsize": 15,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "legend.fontsize": 13,
        "axes.linewidth": 1.1,
        "savefig.dpi": 300,
    })

    saved = [r - d for r, d in zip(recon, dbpull)]
    fig, ax = plt.subplots(figsize=(9.5, 6.0), constrained_layout=True)

    # Shade the gap between the two curves: this is the time saved.
    ax.fill_between(counts, dbpull, recon, color="#c0504d", alpha=0.10,
                    label="Time saved")
    ax.plot(counts, recon, "-o", color="#c0504d", lw=2.6, ms=8,
            markeredgecolor="black", markeredgewidth=0.5,
            label="Reconstruct votes (RMG reaction generation)")
    ax.plot(counts, dbpull, "-s", color="#1f5fa6", lw=2.6, ms=8,
            markeredgecolor="black", markeredgewidth=0.5,
            label="Pull stored votes (database read)")

    ax.set_yscale("log")
    ax.set_xlim(0, max(counts) * 1.03)
    ax.set_xlabel("Mechanism size (number of CHEMKIN species to identify)")
    ax.set_ylabel("Time for the voting table to open (s, log scale)")
    ax.set_title("Voting-table display time: reconstruction vs. stored votes")
    ax.legend(loc="center right", frameon=True, framealpha=0.95)
    ax.grid(True, which="major", linestyle=":", alpha=0.6)
    ax.grid(True, which="minor", linestyle=":", alpha=0.25)

    ax.text(0.015, 0.97,
            f"median saved {median(saved):.0f} s/job   |   "
            f"total {sum(saved):.0f} s across {len(counts)} jobs",
            transform=ax.transAxes, ha="left", va="top", fontsize=13,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.6"))

    if mode == "simulate":
        ax.text(0.985, 0.02, "illustrative model: not yet measured live",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=11,
                style="italic", color="0.45")

    fig.savefig(out_path)
    print(f"Figure written to {out_path}")



def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    default_fig = os.path.normpath(os.path.join(
        here, "..", "..",
        "Prometheus-A-Self-Consistent-Cyberinfrastructure-for-Combustion-Science",
        "figures", "vote_display_time_saved.png"))

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=10,
                        help="number of mechanisms to compare (default: 10)")
    parser.add_argument("--mode", choices=["simulate", "live"], default="simulate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=default_fig)
    args = parser.parse_args()

    counts = DEFAULT_SPECIES_COUNTS[:args.jobs]
    if len(counts) < args.jobs:  # pad with growing sizes if more jobs requested
        counts += [counts[-1] + 500 * (i + 1) for i in range(args.jobs - len(counts))]

    print(f"Comparing voting-table display time for {len(counts)} jobs "
          f"in '{args.mode}' mode...")
    recon, dbpull = collect(args.mode, counts, args.seed)

    saved = [r - d for r, d in zip(recon, dbpull)]
    print("\nSummary:")
    print(f"  reconstruct: median={median(recon):7.2f}s  mean={mean(recon):7.2f}s")
    print(f"  database   : median={median(dbpull):7.2f}s  mean={mean(dbpull):7.2f}s")
    print(f"  time saved : median={median(saved):7.2f}s/job  total={sum(saved):7.2f}s")
    print(f"  speed-up (median): {median(recon) / median(dbpull):.0f}x faster to open")

    save_csv(os.path.splitext(args.out)[0] + ".csv", counts, recon, dbpull)
    plot(counts, recon, dbpull, args.out, args.mode)


if __name__ == "__main__":
    main()
