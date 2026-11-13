"""Use case 4. For which species do the kinetic models disagree most on the enthalpy of formation?"""
# %% Imports
import statistics
from collections import Counter, defaultdict

import matplotlib.pyplot as plt

from chem_tools import h_kj
from prometheus_api import COLOURS, get_all, save, style

# %% All thermochemistry entries of the models (about 20 requests), and the links of every model
entries = {e["id"]: e for e in get_all("/api/thermo/", reference="false")}
models = get_all("/api/kineticmodel/", fields="model_name,thermocomment_set,speciesname_set")

# %% The enthalpy of formation of each species in each model, and the name that most models use
values, names = defaultdict(list), defaultdict(Counter)
for m in models:
    for n in m["speciesname_set"]:
        names[n["species"]][n["name"]] += 1
    for c in m["thermocomment_set"]:
        e = entries.get(c["thermo"])
        if e and e["temp_min_1"] <= 299.15:
            values[e["species"]].append(h_kj(e))

# %% The species in ten or more models, by spread (largest minus smallest value)
rows = sorted(((max(v) - min(v), sid, v) for sid, v in values.items() if len(v) >= 10), reverse=True)
top = rows[:12]
print(f"{len(rows)} species are in ten or more models; spread larger than 1 kcal/mol: "
      f"{sum(r[0] > 4.184 for r in rows)}; larger than 40 kJ/mol: {sum(r[0] > 40 for r in rows)}")
for spread, sid, v in top:
    print(f"  {names[sid].most_common(1)[0][0]:12s} species record {sid:6d}: {len(v):3d} models, "
          f"{min(v):8.1f} to {max(v):8.1f} kJ/mol")

# %% Plot each value minus the median of the models (labels: the names that most models use)
style()
fig, ax = plt.subplots(figsize=(7.0, 4.2))
ax.axvspan(-4.184, 4.184, color="#eaf1f8", zorder=0, lw=0)
for i, (_, sid, v) in enumerate(top):
    ax.scatter([x - statistics.median(v) for x in v], [i] * len(v), s=15, alpha=0.65, color=COLOURS[0],
               edgecolors="white", linewidths=0.3, zorder=3)
ax.axvline(0, color="#1a1a1a", lw=0.9, zorder=2)
ax.set_yticks(range(len(top)), [names[sid].most_common(1)[0][0] for _, sid, _ in top], fontfamily="monospace", fontsize=8)
ax.set_ylim(len(top) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.set_xscale("symlog", linthresh=10)
ax.set_xticks([-500, -100, -10, 0, 10, 100, 500], ["-500", "-100", "-10", "0", "10", "100", "500"])
ax.set_xlabel("Enthalpy of formation at 298.15 K, model minus the median of the models (kJ mol$^{-1}$)")
ax.set_title("The 12 species with the largest spread between the models")
save(fig, "uc04_enthalpy_spread")
