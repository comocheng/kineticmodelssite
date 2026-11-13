"""Use case 13. What laminar burning velocities of methane-air flames at 1 atm and 298 K does the
collection hold, and do the laboratories agree?"""
from collections import defaultdict

import matplotlib.pyplot as plt

from prometheus_api import get_all, save, style

CH4, O2, N2 = "1S/CH4/h1H4", "1S/O2/c1-2", "1S/N2/c1-2"
# Burning velocities of mixtures with CH4, at 0.9 to 1.1 bar and 290 to 305 K (SI values: Pa and K)
rows = get_all("/api/laminar-burning-velocity/", inchi=CH4, datapoint__pressure__gte=90000,
               datapoint__pressure__lte=110000, datapoint__temperature__gte=290,
               datapoint__temperature__lte=305, expand="datapoint")
ids = sorted({r["datapoint"]["dataset"] for r in rows})
datasets = {d["id"]: d for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, ids)),
                                        fields="id,reference_doi,chemked_file_path,common_properties")}


def mixture(dp):
    """Mole fractions by InChI: the composition of the datapoint, or the common composition of its dataset."""
    comp = dp["composition"] or (datasets[dp["dataset"]]["common_properties"] or {}).get("composition")
    return {s["inchi"]: s["amount"] for s in (comp or {}).get("species", [])}


by_paper = defaultdict(list)
for r in rows:
    x = mixture(r["datapoint"])
    if set(x) != {CH4, O2, N2} or not 3.6 <= x[N2] / x[O2] <= 3.9:   # methane-air only
        continue
    d = datasets[r["datapoint"]["dataset"]]
    paper = d["chemked_file_path"].split("/")[-2].replace("_", " ")   # the paper folder: first author and year
    by_paper[paper].append((2 * x[CH4] / x[O2], r["laminar_burning_velocity"] * 100))
n = sum(len(v) for v in by_paper.values())
print(f"{len(rows)} burning velocities with CH4 at about 1 atm and 298 K; {n} are methane-air, "
      f"from {len(by_paper)} papers")
near1 = [v for pts in by_paper.values() for phi, v in pts if abs(phi - 1) < 0.02]
print(f"  at phi = 0.98 to 1.02: {len(near1)} values from {min(near1):.1f} to {max(near1):.1f} cm/s")

style()
fig, ax = plt.subplots(figsize=(6.8, 4.2))
markers = "osD^v<>ph*X"
for k, (paper, pts) in enumerate(sorted(by_paper.items(), key=lambda kv: -len(kv[1]))):
    phi, v = zip(*sorted(pts))
    ax.plot(phi, v, markers[k % len(markers)], ms=4, alpha=0.8, label=paper if k < 12 else None)
ax.set_xlabel("Equivalence ratio $\\phi$ (from the mixture)")
ax.set_ylabel("Laminar burning velocity (cm/s)")
ax.set_title(f"Methane-air, 1 atm, 298 K: {n} values from {len(by_paper)} papers", loc="left", fontsize=10)
ax.legend(fontsize=7, ncol=2, title="paper (the 12 with the most values)", title_fontsize=7)
save(fig, "uc13_burning_velocity")
