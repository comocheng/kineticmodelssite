"""Use case 19. Do newer kinetic models use enthalpies of formation that are closer to the Active
Thermochemical Tables (ATcT)?"""
# %% Imports
import re
import statistics

import matplotlib.pyplot as plt
from scipy.stats import spearmanr

from chem_tools import h_kj
from prometheus_api import COLOURS, get_all, links, save, style

# %% The ATcT enthalpies of formation at 298.15 K (kJ/mol), by species record
atct = {r["species"]: r["enthalpy_298"] / 1000 for r in get_all("/api/thermo-record/", provider="atct")}

# %% The thermochemistry entries of the models (about 20 requests), and the entries of each model
entries = {e["id"]: e for e in get_all("/api/thermo/", reference="false")}
per_model = {m: [entries[t] for t in ids if t in entries and entries[t]["temp_min_1"] <= 299.15]
             for m, ids in links("thermo").items()}

# %% The core species: species with an ATcT value that at least half of the models contain
present = [{e["species"] for e in es} & atct.keys() for es in per_model.values()]
core = {s for s in atct if sum(s in p for p in present) >= 0.5 * len(present)}

# %% The year in the model name: "CombFlame2015/3755-Konnov" and "NitrogenGlarborg2018", not "butanol/2028-Sarathy"
def year(model):
    found = re.search(r"(?<=[A-Za-z])(?:19|20)\d\d(?=[/_]|$)", model)
    return int(found.group()) if found else None

# %% For each model with a year and most core species: the share of core species off by more than 1 kcal/mol
rows = []
for model, es in per_model.items():
    diffs = [abs(h_kj(e) - atct[e["species"]]) for e in es if e["species"] in core]
    if year(model) and len(diffs) >= 0.8 * len(core):
        rows.append((year(model), statistics.median(diffs), 100 * sum(d > 4.184 for d in diffs) / len(diffs), model))
rho, p = spearmanr([r[0] for r in rows], [r[2] for r in rows])
print(f"{len(atct)} ATcT records; {len(core)} core species; {len(rows)} models with a year in the name "
      f"({len(per_model) - len(rows)} without a year or with too few core species)")
print(f"Spearman correlation of the year and the share off by more than 1 kcal/mol: {rho:.2f} (p = {p:.2f})")
for y in sorted({r[0] for r in rows}):
    sel = [r for r in rows if r[0] == y]
    print(f"  {y}: {len(sel):2d} models, median |difference| {statistics.median(r[1] for r in sel):.2f} kJ/mol, "
          f"{statistics.mean(r[2] for r in sel):4.1f} % of the core species off by more than 1 kcal/mol")

# %% Plot the share of each model against its year (a small sideways shift keeps equal points apart)
style()
fig, ax = plt.subplots(figsize=(7.0, 3.6))
x = [r[0] + 0.5 * ((k * 0.618) % 1 - 0.5) for k, r in enumerate(rows)]
ax.scatter(x, [r[2] for r in rows], s=22, color=COLOURS[0], alpha=0.75, edgecolors="white", linewidths=0.4, zorder=3)
for xi, r in sorted(zip(x, rows), key=lambda t: -t[1][2])[:3]:
    ax.annotate(r[3], (xi, r[2]), xytext=(5, 0), textcoords="offset points", fontsize=7, va="center")
ax.set_xlabel("Year in the model name")
ax.set_ylabel("Core species off by more than\n1 kcal mol$^{-1}$ from ATcT (%)")
ax.set_title(f"Enthalpy of formation of {len(core)} core species: Spearman ρ = {rho:.2f} (p = {p:.2f})")
save(fig, "uc19_enthalpy_by_model_year")
