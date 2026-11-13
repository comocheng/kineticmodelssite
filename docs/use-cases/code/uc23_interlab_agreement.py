"""Use case 23. When different laboratories measure the laminar burning velocity of the same fuel-air
flame, do their values agree within the uncertainties that they report?"""
# %% Imports
import math
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from prometheus_api import COLOURS, get_all, save, style

O2, N2 = "1S/O2/c1-2", "1S/N2/c1-2"

# %% All burning velocities with their datapoints, and the paper (DOI) of each dataset
rows = get_all("/api/laminar-burning-velocity/", expand="datapoint")
doi = {d["id"]: d["reference_doi"] or f"dataset {d['id']}"
       for d in get_all("/api/experiment-dataset/", experiment_type="laminar burning velocity measurement", fields="id,reference_doi")}

# %% Keep fuel-air flames with a reported uncertainty, and give each the equivalence ratio of its mixture
def reported(r):
    """The reported uncertainty in cm/s, or None. The value and its uncertainty are in the units of the file."""
    q = r["laminar_burning_velocity_quantity"]
    if q["uncertainty_sourcetype"] != "reported" or q["uncertainty"] is None:
        return None
    to_cm_s = 100 * r["laminar_burning_velocity"] / q["value"]
    return q["uncertainty"] * (q["value"] if q["uncertainty_type"] == "relative" else 1) * to_cm_s

flames = defaultdict(list)   # (fuel, T, p, phi) -> [(paper, value, uncertainty)]
for r in rows:
    dp = r["datapoint"]
    x = {s["inchi"]: s for s in dp["composition"]["species"]}
    fuel = [s for i, s in x.items() if i not in (O2, N2)]
    if len(x) != 3 or O2 not in x or N2 not in x or not 3.6 <= x[N2]["amount"] / x[O2]["amount"] <= 3.9 or not reported(r):
        continue
    atoms = {a["element"]: a["amount"] for a in fuel[0]["atomic_composition"]}
    o2_needed = atoms.get("C", 0) + atoms.get("H", 0) / 4 - atoms.get("O", 0) / 2   # mol O2 for 1 mol fuel
    phi = fuel[0]["amount"] / x[O2]["amount"] * o2_needed
    key = (fuel[0]["species_name"], 5 * round(dp["temperature"] / 5), round(math.log(dp["pressure"]) / math.log(1.05)),
           round(phi / 0.05) * 0.05)
    flames[key].append((doi[dp["dataset"]], 100 * r["laminar_burning_velocity"], reported(r)))

# %% For each value: (value - mean of the other papers) / reported uncertainty, in flames from 2 or more papers
z, fuel_of = [], []
for key, values in flames.items():
    for paper, v, u in values:
        others = [w for p, w, _ in values if p != paper]
        if others:
            z.append((v - np.mean(others)) / u)
            fuel_of.append(key[0])
z = np.array(z)
shared = [k for k, v in flames.items() if len({p for p, _, _ in v}) >= 2]
print(f"{sum(map(len, flames.values()))} fuel-air burning velocities with a reported uncertainty; "
      f"{len(shared)} flames (same fuel, T, p and phi) measured by 2 or more papers, {len(z)} values")
small = [u / v for values in flames.values() for _, v, u in values if u < 0.01 * v]
print(f"  |z| > 2 for {100 * np.mean(abs(z) > 2):.1f} % of the values (about 5 % if the uncertainties are right); "
      f"median |z| {np.median(abs(z)):.2f} (0.67 for a normal distribution)")
print(f"  {len(small)} reported uncertainties are less than 1 % of the value")
for fuel in sorted(set(fuel_of), key=lambda f: -fuel_of.count(f)):
    sel = z[[f == fuel for f in fuel_of]]
    print(f"  {fuel:12s} {len(sel):4d} values; |z| > 2 for {100 * np.mean(abs(sel) > 2):5.1f} %; median |z| {np.median(abs(sel)):.2f}")

# %% Plot the distribution of z, with the normal distribution that correct uncertainties would give
style()
fig, ax = plt.subplots(figsize=(7.0, 3.4))
bins = np.linspace(-6, 6, 49)
ax.hist(np.clip(z, -6, 6), bins=bins, density=True, color=COLOURS[0], edgecolor="white", lw=0.3, label=f"{len(z)} values")
t = np.linspace(-6, 6, 200)
ax.plot(t, np.exp(-t ** 2 / 2) / np.sqrt(2 * np.pi), color=COLOURS[1], lw=1.6, label="normal distribution, σ = 1")
ax.set_xlabel("(value − mean of the other papers) / reported uncertainty  (values beyond ±6 at ±6)")
ax.set_ylabel("Probability density")
ax.set_title(f"Fuel-air burning velocities measured by 2 or more papers: |z| > 2 for {100 * np.mean(abs(z) > 2):.0f} %")
ax.legend(loc="upper left")
save(fig, "uc23_interlab_agreement")
