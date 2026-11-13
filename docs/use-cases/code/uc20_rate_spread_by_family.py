"""Use case 20. For which reaction families do the kinetic models disagree most on the rate
coefficient of the same reaction? The reaction records give the RMG reaction family."""
# %% Imports
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import rate_k
from prometheus_api import COLOURS, get_all, links, save, style

# %% All reaction records (their RMG family), all rate records, and the rate records of each model
family = {r["id"]: r["rmg_family"] for r in get_all("/api/reaction/")}
records = {k["id"]: k for k in get_all("/api/kinetics/")}
model_links = links("kinetics")

# %% k(1000 K, 1 bar) of each reaction in each model (the sum of its rate records: duplicate reactions)
k = defaultdict(lambda: defaultdict(float))
for model, ids in model_links.items():
    for i in ids:
        r = records.get(i)
        if r and not r["specific_collider"]:
            k[r["reaction"]][model] += rate_k(r, 1000.0)

# %% The spread of each reaction that at least 3 models give: largest k / smallest k
spread = defaultdict(list)
for reaction, by_model in k.items():
    values = [v for v in by_model.values() if v > 0]
    if len(values) >= 3:
        name = family.get(reaction) if family.get(reaction) not in ("", "-", "?", None) else "no RMG family"
        spread[name].append(np.log10(max(values) / min(values)))
top = sorted((f for f in spread if len(spread[f]) >= 20), key=lambda f: -np.mean(np.array(spread[f]) > np.log10(2)))
BINS = [("equal (factor below 1.1)", 0, np.log10(1.1)), ("1.1 to 2", np.log10(1.1), np.log10(2)),
        ("2 to 10", np.log10(2), 1), ("more than 10", 1, np.inf)]
share = {f: [100 * np.mean((np.array(spread[f]) >= lo) & (np.array(spread[f]) < hi)) for _, lo, hi in BINS] for f in top}
print(f"{sum(map(len, spread.values()))} reactions in at least 3 models; families with 20 or more such reactions:")
for f in top:
    print(f"  {f:36s} {len(spread[f]):5d} reactions; " + ", ".join(f"{b[0]} {v:4.1f} %" for b, v in zip(BINS, share[f])))

# %% Plot the share of the reactions of each family in four classes of disagreement
style()
fig, ax = plt.subplots(figsize=(7.0, 0.3 * len(top) + 1.3))
left = np.zeros(len(top))
for (label, _, _), colour, k in zip(BINS, ["#d9d9d9", COLOURS[5], COLOURS[0], COLOURS[1]], range(4)):
    width = np.array([share[f][k] for f in top])
    ax.barh(range(len(top)), width, left=left, color=colour, height=0.7, label=label)
    left += width
ax.set_yticks(range(len(top)), [f"{f} ({len(spread[f])})" for f in top], fontsize=7.5)
ax.set_ylim(len(top) - 0.5, -0.5)
ax.set_xlim(0, 100)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xlabel("Reactions of the family (%)")
ax.set_title("Largest / smallest k of one reaction between the models, 1000 K and 1 bar", pad=24)
ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2, fontsize=7.5)
save(fig, "uc20_rate_spread_by_family")
