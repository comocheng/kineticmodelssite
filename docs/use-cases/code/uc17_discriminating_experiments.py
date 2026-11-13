"""Use case 17. Five small hydrogen models are simulated in PyTeCK for every shock-tube dataset of
H2/O2 ignition. Which experiments give the largest differences between the models, compared with
the scatter of the data, and can thus show which model is right?"""
# %% Imports
import itertools
import statistics
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from prometheus_api import COLOURS, get, get_all, get_text, model_names, model_record, paper, save, style
from pyteck_tools import run_pyteck, species_key

MODELS = ["CombFlame2015/3755-Konnov", "PCI2015/0153-Marshall", "CombFlame2017/45-Olm", "CombFlame2014/711-Allen", "H2-3"]
ONLY = {"1S/H2/h1H", "1S/O2/c1-2", "1S/Ar", "1S/N2/c1-2", "1S/He"}

# %% The shock-tube datasets whose mixtures hold only H2, O2 and diluents
delays = get_all("/api/ignition-delay/", inchi="1S/H2/h1H", expand="datapoint", fields="datapoint")
pure = {d["datapoint"]["dataset"] for d in delays if {s["inchi"] for s in d["datapoint"]["composition"]["species"]} <= ONLY}
datasets = [d for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, sorted(pure))),
                               fields="id,chemked_file_path,apparatus") if d["apparatus"]["kind"] == "shock tube"]

# %% The five models: their Cantera files and their species names
models = {}
for name in MODELS:
    m = model_record(name)
    models[name] = (get_text(f"/kineticmodel/{m['id']}/download/cantera"), model_names(m["id"]))

# %% Simulate each dataset with each model (a dataset that a model cannot simulate is left out)
results = {}
for d in datasets:
    chemked = get_text(f"/chemked/dataset/{d['id']}/export/", format="yaml")
    try:
        runs = {name: run_pyteck(chemked, cantera, species_key(chemked, names)) for name, (cantera, names) in models.items()}
    except KeyError as missing:
        print(f"  left out dataset {d['id']}: {missing}")
        continue
    results[d["id"]] = runs

# %% Discrimination D: the spread of ln(simulated delay) between the models, divided by the scatter sigma of the data
rows, no_ignition = [], []
for did, runs in results.items():
    first, _, sigma = next(iter(runs.values()))
    measured = np.array([r[2] for r in first])
    sim = np.array([[r[3] for r in rows_] for rows_, _, _ in runs.values()])     # models x datapoints
    ok = (sim > 0).all(axis=0)   # PyTeCK gives 0 when it finds no ignition in the simulation
    if ok.sum() < 3 or not all(np.isfinite(E) for _, E, _ in runs.values()):
        no_ignition.append(did)
        continue
    ratio = dict(zip(runs, np.median(sim[:, ok] / measured[ok], axis=1)))   # simulated / measured delay
    rows.append(dict(id=did, D=float(np.median(np.log(sim[:, ok]).std(axis=0)) / sigma), sigma=sigma, ratio=ratio,
                     E={m: r[1] for m, r in runs.items()}, p=statistics.median(r[1] for r in first),
                     T=statistics.median(r[0] for r in first), n=len(first)))
rows.sort(key=lambda r: -r["D"])
paper_of = {d["id"]: paper(d) for d in datasets}
print(f"{len(rows)} datasets simulated with {len(MODELS)} models ({sum(r['n'] for r in rows)} datapoints); "
      f"left out {len(no_ignition)} datasets in which a model gives no ignition: {no_ignition}")

# %% The datasets with D > 1: which model agrees with the data, and which models agree with each other
strong = [r for r in rows if r["D"] > 1]
inside = {m: sum(abs(np.log(r["ratio"][m])) <= r["sigma"] for r in strong) for m in MODELS}   # within the data scatter
print(f"model spread larger than the data scatter (D > 1) in {len(strong)} datasets, at "
      f"{min(r['T'] for r in strong):.0f} to {max(r['T'] for r in strong):.0f} K (median temperature of a dataset)")
weak = sorted(round(r["T"]) for r in rows if r["D"] <= 1)
print(f"  D < 1 in {len(weak)} datasets; their median temperatures (K): {weak}")
print("in the datasets with D > 1, the model's median delay is within the data scatter of the measured delay in:")
for m in sorted(MODELS, key=lambda m: -inside[m]):
    print(f"  {m:28s} {inside[m]:2d} of {len(strong)} datasets (mean E over all datasets {np.mean([r['E'][m] for r in rows]):.1f})")
shortest = Counter(min(r["ratio"], key=r["ratio"].get) for r in strong)
print("model with the shortest delay of the five: " + ", ".join(f"{m} in {n}" for m, n in shortest.most_common()))
apart = {pair: np.median([abs(np.log(r["ratio"][pair[0]] / r["ratio"][pair[1]])) for r in strong])
         for pair in itertools.combinations(MODELS, 2)}
a, b = min(apart, key=apart.get)
print(f"closest two models: {a} and {b}, median difference of their delays {100 * np.expm1(apart[a, b]):.1f} %")
for r in rows[:6]:
    print(f"  dataset {r['id']} ({paper_of[r['id']]}, {r['p']:.1f} bar, {r['T']:.0f} K): D = {r['D']:.2f}; simulated / measured: "
          + ", ".join(f"{m.split('-', 1)[-1] if '/' in m else m} {r['ratio'][m]:.2f}" for m in MODELS))

# %% Plot: for each dataset with D > 1, the simulated / measured delay of each model and the scatter of the data
style()
fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 1.3 + 0.19 * len(strong)), sharey=True,
                             gridspec_kw=dict(width_ratios=[4.2, 1], wspace=0.06))
y = np.arange(len(strong))
ax.barh(y, [np.exp(r["sigma"]) - np.exp(-r["sigma"]) for r in strong], left=[np.exp(-r["sigma"]) for r in strong],
        height=0.72, color="#e3e3e3", label="scatter of the data ($\\pm\\sigma$)", zorder=1)
ax.axvline(1, color="#333333", lw=0.8, zorder=2)
for m, colour, marker in zip(MODELS, COLOURS, "osD^v"):
    ax.scatter([r["ratio"][m] for r in strong], y, color=colour, marker=marker, s=22, edgecolors="white",
               linewidths=0.4, zorder=3, label=f"{m}: {inside[m]}")
linked = next(i for i, r in enumerate(strong) if r["id"] == 1733)
ax.annotate("use case 18", (1.45, linked), xytext=(1.9, linked), va="center", fontsize=7.5, color="#555555",
            arrowprops=dict(arrowstyle="-", color="#999999", lw=0.6))
ax.set_xscale("log")
ticks = [0.25, 0.5, 1, 2, 4, 8, 16]
ax.set_xlim(0.25, 1.4 * max(v for r in strong for v in r["ratio"].values()))
ax.set_xticks(ticks, [f"{v:g}" for v in ticks])
ax.minorticks_off()
ax.set_yticks(y, [f"{paper_of[r['id']]} ({r['id']}), {r['p']:.0f} bar, {r['T']:.0f} K" for r in strong])
ax.invert_yaxis()
ax.set_xlabel("Simulated / measured ignition delay")
ax.grid(axis="y", visible=False)
bx.barh(y, [r["D"] for r in strong], height=0.6, color="#999999")
bx.axvline(1, color=COLOURS[1], lw=0.9, ls=(0, (4, 2)))
bx.set_xticks([0, 1, 4, 8])
bx.set_xlim(0, 1.1 * strong[0]["D"])
bx.set_xlabel("D")
bx.grid(axis="y", visible=False)
bx.tick_params(axis="y", length=0)
ax.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=3, columnspacing=1.0, handletextpad=0.2,
          borderaxespad=0.3, title=f"Model: number of the {len(strong)} datasets in which it is inside the grey band",
          title_fontproperties=dict(size=8), alignment="left")
save(fig, "uc17_discriminating_experiments")
