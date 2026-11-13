"""Use case 25. Five small hydrogen models are simulated in PyTeCK for every shock-tube dataset of
H2/O2 ignition. Which experiments give the largest differences between the models, compared with
the scatter of the data, and can thus show which model is right?"""
# %% Imports
import statistics

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

# %% Discrimination: the spread of ln(simulated delay) between the models, divided by the scatter sigma of the data
rows, no_ignition = [], []
for did, runs in results.items():
    first, _, sigma = next(iter(runs.values()))
    sim = np.array([[r[3] for r in rows_] for rows_, _, _ in runs.values()])     # models x datapoints
    ok = (sim > 0).all(axis=0)   # PyTeCK gives 0 when it finds no ignition in the simulation
    if ok.sum() < 3 or not all(np.isfinite(E) for _, E, _ in runs.values()):
        no_ignition.append(did)
        continue
    rows.append(dict(id=did, D=float(np.median(np.log(sim[:, ok]).std(axis=0)) / sigma), E={m: r[1] for m, r in runs.items()},
                     p=statistics.median(r[1] for r in first), T=statistics.median(r[0] for r in first), n=len(first)))
rows.sort(key=lambda r: -r["D"])
paper_of = {d["id"]: paper(d) for d in datasets}
print(f"{len(rows)} datasets simulated with {len(MODELS)} models ({sum(r['n'] for r in rows)} datapoints); "
      f"left out {len(no_ignition)} datasets in which a model gives no ignition: {no_ignition}")
print(f"  model spread larger than the data scatter (D > 1) in {sum(r['D'] > 1 for r in rows)} datasets")
print("  mean PyTeCK error function E over the datasets: " +
      ", ".join(f"{m} {np.mean([r['E'][m] for r in rows]):.1f}" for m in MODELS))
for r in rows[:6]:
    best = min(r["E"], key=r["E"].get)
    print(f"  dataset {r['id']} ({paper_of[r['id']]}, {r['p']:.1f} bar, {r['T']:.0f} K): D = {r['D']:.2f}; "
          f"lowest E {r['E'][best]:.1f} ({best}), highest E {max(r['E'].values()):.1f}")

# %% Plot D of each dataset against its pressure, coloured by its temperature
style()
fig, ax = plt.subplots(figsize=(7.0, 3.6))
sc = ax.scatter([r["p"] for r in rows], [r["D"] for r in rows], c=[r["T"] for r in rows], cmap="viridis",
                s=[12 + 2 * r["n"] for r in rows], edgecolors="white", linewidths=0.4, zorder=3)
fig.colorbar(sc, ax=ax, pad=0.02, label="Median temperature (K)")
for r in rows[:3]:
    ax.annotate(f"{paper_of[r['id']]} ({r['id']})", (r["p"], r["D"]), xytext=(6, 0), textcoords="offset points",
                fontsize=7, va="center")
ax.axhline(1, color=COLOURS[1], lw=0.9, ls=(0, (4, 2)), label="model spread = data scatter")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Median pressure of the dataset (bar)")
ax.set_ylabel("Spread of the models / scatter of the data")
ax.set_title(f"Which H$_2$ shock-tube datasets discriminate between {len(MODELS)} models (marker size: datapoints)")
ax.legend(loc="upper left")
save(fig, "uc25_discriminating_experiments")
