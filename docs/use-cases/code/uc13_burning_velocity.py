"""Use case 13. What laminar burning velocities of methane-air flames at 1 atm and 298 K does the
collection hold, and do the laboratories agree?"""
# %% Imports
from collections import defaultdict

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, paper, save, style

# %% Burning velocities of mixtures with CH4 at 0.9 to 1.1 bar and 290 to 305 K (SI values: Pa and K)
CH4, O2, N2 = "1S/CH4/h1H4", "1S/O2/c1-2", "1S/N2/c1-2"
rows = get_all("/api/laminar-burning-velocity/", inchi=CH4, datapoint__pressure__gte=90000, datapoint__pressure__lte=110000,
               datapoint__temperature__gte=290, datapoint__temperature__lte=305, expand="datapoint")
ids = sorted({r["datapoint"]["dataset"] for r in rows})
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, ids)),
                                        fields="id,chemked_file_path,common_properties")}

# %% The mixture of each datapoint (its own composition, or the common one of its dataset); keep methane-air
def mixture(dp):
    comp = dp["composition"] or (datasets[dp["dataset"]]["common_properties"] or {}).get("composition")
    return {s["inchi"]: s["amount"] for s in (comp or {}).get("species", [])}

by_paper = defaultdict(list)
for r in rows:
    x = mixture(r["datapoint"])
    if set(x) == {CH4, O2, N2} and 3.6 <= x[N2] / x[O2] <= 3.9:
        by_paper[paper(datasets[r["datapoint"]["dataset"]])].append((2 * x[CH4] / x[O2], r["laminar_burning_velocity"] * 100))
n = sum(map(len, by_paper.values()))
near1 = [v for pts in by_paper.values() for phi, v in pts if abs(phi - 1) < 0.02]
print(f"{len(rows)} burning velocities with CH4 at about 1 atm and 298 K; {n} are methane-air, from {len(by_paper)} papers")
print(f"  at phi = 0.98 to 1.02: {len(near1)} values from {min(near1):.1f} to {max(near1):.1f} cm/s")

# %% Plot the burning velocity against phi, one marker for each paper
style()
fig, ax = plt.subplots(figsize=(7.0, 4.2))
for k, (name, pts) in enumerate(sorted(by_paper.items(), key=lambda kv: -len(kv[1]))):
    phi, v = zip(*sorted(pts))
    ax.plot(phi, v, "osD^v<>ph*XPd8"[k % 14], ms=4.5, mec="white", mew=0.4, color=COLOURS[k % len(COLOURS)],
            alpha=0.9, label=name)
ax.set_xlabel("Equivalence ratio $\\phi$ (calculated from the mixture)")
ax.set_ylabel("Laminar burning velocity (cm s$^{-1}$)")
ax.set_title(f"Methane-air at 1 atm and 298 K: {n} values from {len(by_paper)} papers")
ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7.5)
save(fig, "uc13_burning_velocity")
