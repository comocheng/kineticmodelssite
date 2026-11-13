"""Use case 11. At which temperatures and pressures did the experiments of the collection measure
their data?"""
# %% Imports
from collections import defaultdict

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, style

# %% The conditions of every datapoint, and the type and apparatus of every dataset (fields= keeps them small)
points = get_all("/api/experiment-datapoint/", fields="id,temperature,pressure,dataset")
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", fields="id,experiment_type,apparatus")}

# %% Group the datapoints by experiment type; ignition delays also by apparatus
def group(dataset):
    """Most rapid-compression-machine datapoints give T and p before compression, not the compressed state."""
    if dataset["experiment_type"] != "ignition delay":
        return dataset["experiment_type"]
    if (dataset["apparatus"] or {}).get("kind") == "rapid compression machine":
        return "ignition delay, rapid compression machine (state before compression)"
    return "ignition delay, shock tube and others"

groups = defaultdict(list)
for p in points:
    if p["temperature"] and p["pressure"]:
        groups[group(datasets[p["dataset"]])].append((p["temperature"], p["pressure"] / 1e5))
groups = dict(sorted(groups.items(), key=lambda kv: -len(kv[1])))
print(f"{len(points)} datapoints in {len(datasets)} datasets")
for g, tp in groups.items():
    T, P = zip(*tp)
    print(f"  {g:70s} {len(tp):6d} datapoints; T {min(T):5.0f} to {max(T):5.0f} K; p {min(P):7.3f} to {max(P):6.1f} bar")

# %% Plot the conditions (rasterized: the points are an image inside the vector file)
style()
fig, ax = plt.subplots(figsize=(7.0, 4.3))
for (g, tp), colour in zip(groups.items(), COLOURS):
    T, P = zip(*tp)
    ax.scatter(T, P, s=4, alpha=0.45, color=colour, edgecolors="none", label=f"{g} ({len(tp)})", rasterized=True)
ax.set_yscale("log")
ax.set_xlabel("Temperature of the datapoint (K)")
ax.set_ylabel("Pressure of the datapoint (bar)")
ax.legend(markerscale=3, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
save(fig, "uc11_experiment_coverage")
