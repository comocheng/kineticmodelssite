"""Use case 11. At which temperatures and pressures did the experiments of the collection measure
their data?"""
from collections import Counter

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, style

# fields= keeps the responses small: only the conditions and the dataset of each datapoint
points = get_all("/api/experiment-datapoint/", fields="id,temperature,pressure,dataset")
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", fields="id,experiment_type,apparatus")}


def group(dataset):
    """The experiment type, with ignition delays divided by apparatus. Most rapid-compression-machine
    datapoints give the temperature and pressure before compression, not the compressed state."""
    t, kind = dataset["experiment_type"], (dataset["apparatus"] or {}).get("kind", "")
    if t == "ignition delay":
        return ("ignition delay, rapid compression machine (state before compression)"
                if kind == "rapid compression machine" else "ignition delay, shock tube and others")
    return t


groups = Counter(group(datasets[p["dataset"]]) for p in points)
print(f"{len(points)} datapoints in {len(datasets)} datasets")
for g, n in groups.most_common():
    sel = [p for p in points if group(datasets[p["dataset"]]) == g and p["temperature"] and p["pressure"]]
    print(f"  {g:70s} {n:6d} datapoints; T {min(p['temperature'] for p in sel):5.0f} to "
          f"{max(p['temperature'] for p in sel):5.0f} K; p {min(p['pressure'] for p in sel) / 1e5:7.3f} to "
          f"{max(p['pressure'] for p in sel) / 1e5:6.1f} bar")

style()
fig, ax = plt.subplots(figsize=(7.0, 4.3))
for (g, _), colour in zip(groups.most_common(), COLOURS):
    sel = [p for p in points if group(datasets[p["dataset"]]) == g and p["temperature"] and p["pressure"]]
    # rasterized: the points are an image inside the vector file, so the file stays small
    ax.scatter([p["temperature"] for p in sel], [p["pressure"] / 1e5 for p in sel], s=4, alpha=0.45,
               color=colour, edgecolors="none", label=f"{g} ({len(sel)})", rasterized=True)
ax.set_yscale("log")
ax.set_xlabel("Temperature of the datapoint (K)")
ax.set_ylabel("Pressure of the datapoint (bar)")
ax.legend(markerscale=3, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
save(fig, "uc11_experiment_coverage")
