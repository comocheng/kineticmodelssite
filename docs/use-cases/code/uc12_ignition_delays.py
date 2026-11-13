"""Use case 12. Which shock-tube ignition delays of stoichiometric n-heptane mixtures does the
collection hold, and how do they depend on temperature and pressure?"""
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from prometheus_api import get_all, save, style

HEPTANE = "1S/C7H16/c1-3-5-7-6-4-2/h3-7H2,1-2H3"
# The filters select the mixtures with n-heptane and an equivalence ratio of 0.9 to 1.1; expand=datapoint
# gives the temperature and pressure of each datapoint in the same response
delays = get_all("/api/ignition-delay/", inchi=HEPTANE, datapoint__equivalence_ratio__gte=0.9,
                 datapoint__equivalence_ratio__lte=1.1, expand="datapoint")
ids = sorted({d["datapoint"]["dataset"] for d in delays})
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, ids)),
                                        fields="id,reference_doi,reference_year,apparatus")}
shock = [d for d in delays if (datasets[d["datapoint"]["dataset"]]["apparatus"] or {}).get("kind") == "shock tube"]
papers = {datasets[d["datapoint"]["dataset"]]["reference_doi"] for d in shock}
print(f"{len(delays)} ignition delays of n-heptane at phi = 0.9 to 1.1 in {len(ids)} datasets")
print(f"  {len(shock)} from shock tubes, in {len({d['datapoint']['dataset'] for d in shock})} datasets "
      f"of {len(papers)} papers")
p = [d["datapoint"]["pressure"] / 1e5 for d in shock]
print(f"  pressures {min(p):.1f} to {max(p):.1f} bar; temperatures "
      f"{min(d['datapoint']['temperature'] for d in shock):.0f} to {max(d['datapoint']['temperature'] for d in shock):.0f} K")

style()
fig, ax = plt.subplots(figsize=(7.0, 4.0))
sc = ax.scatter([1000 / d["datapoint"]["temperature"] for d in shock], [d["ignition_delay"] * 1e3 for d in shock],
                c=p, cmap="viridis", norm=LogNorm(), s=18, edgecolors="white", linewidths=0.3, zorder=3)
fig.colorbar(sc, ax=ax, label="Pressure (bar)", pad=0.02)
ax.set_yscale("log")
ax.set_xlabel("1000 K / T")
ax.set_ylabel("Ignition delay (ms)")
top = ax.secondary_xaxis("top", functions=(lambda v: 1000 / v, lambda t: 1000 / t))
top.set_xticks([1600, 1400, 1200, 1000, 900, 800, 700])
top.set_xlabel("Temperature (K)", fontsize=8.5)
ax.set_title(f"n-Heptane, $\\phi$ = 0.9 to 1.1, shock tubes: {len(shock)} datapoints from {len(papers)} papers", pad=30)
save(fig, "uc12_ignition_delays")
