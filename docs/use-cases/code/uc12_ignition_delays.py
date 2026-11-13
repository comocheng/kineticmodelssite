"""Use case 12. Which shock-tube ignition delays of stoichiometric n-heptane mixtures does the
collection hold, and how do they depend on temperature and pressure?"""
# %% Imports
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from prometheus_api import get_all, save, style, temperature_axis

# %% Ignition delays of mixtures with n-heptane at phi = 0.9 to 1.1 (expand=datapoint adds T and p)
delays = get_all("/api/ignition-delay/", inchi="1S/C7H16/c1-3-5-7-6-4-2/h3-7H2,1-2H3",
                 datapoint__equivalence_ratio__gte=0.9, datapoint__equivalence_ratio__lte=1.1, expand="datapoint")

# %% The datasets of these delays; keep the shock tubes
ids = sorted({d["datapoint"]["dataset"] for d in delays})
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, ids)),
                                        fields="id,reference_doi,apparatus")}
shock = [d for d in delays if (datasets[d["datapoint"]["dataset"]]["apparatus"] or {}).get("kind") == "shock tube"]
papers = {datasets[d["datapoint"]["dataset"]]["reference_doi"] for d in shock}
T = [d["datapoint"]["temperature"] for d in shock]
P = [d["datapoint"]["pressure"] / 1e5 for d in shock]
print(f"{len(delays)} ignition delays of n-heptane at phi = 0.9 to 1.1 in {len(ids)} datasets")
print(f"  {len(shock)} from shock tubes, in {len({d['datapoint']['dataset'] for d in shock})} datasets of {len(papers)} papers")
print(f"  pressures {min(P):.1f} to {max(P):.1f} bar; temperatures {min(T):.0f} to {max(T):.0f} K")

# %% Plot the delays against 1000/T, coloured by pressure
style()
fig, ax = plt.subplots(figsize=(7.0, 4.0))
sc = ax.scatter([1000 / t for t in T], [d["ignition_delay"] * 1e3 for d in shock], c=P, cmap="viridis", norm=LogNorm(),
                s=18, edgecolors="white", linewidths=0.3, zorder=3)
fig.colorbar(sc, ax=ax, label="Pressure (bar)", pad=0.02)
ax.set_yscale("log")
ax.set_xlabel("1000 K / T")
ax.set_ylabel("Ignition delay (ms)")
temperature_axis(ax, [1600, 1400, 1200, 1000, 900, 800, 700])
ax.set_title(f"n-Heptane, $\\phi$ = 0.9 to 1.1, shock tubes: {len(shock)} datapoints from {len(papers)} papers", pad=30)
save(fig, "uc12_ignition_delays")
