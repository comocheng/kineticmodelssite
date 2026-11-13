"""Use case 21. Some kinetic models give a reaction in both directions, with one rate expression for
each direction. Do the two rate coefficients obey detailed balance with the model's own thermochemistry?"""
# %% Imports
import math
from collections import Counter, defaultdict

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import log_kc, rate_k
from prometheus_api import COLOURS, get_all, links, save, style

# %% All reaction records and all rate records (about 100 requests)
reactions = {r["id"]: r for r in get_all("/api/reaction/")}
records = {k["id"]: k for k in get_all("/api/kinetics/")}
coeffs = lambda rid: {s["species"]: s["coeff"] for s in reactions[rid]["stoichiometry_set"]}

# %% In each model: k of each reaction record (the sum of its rate records), at 1000 K and 1 bar
T = 1000.0
k = defaultdict(lambda: defaultdict(float))
for model, ids in links("kinetics").items():
    for i in ids:
        if i in records and not records[i]["specific_collider"]:
            k[model][records[i]["reaction"]] += rate_k(records[i], T)

# %% The pairs: two reaction records of one model with the same canonical_key, in opposite directions
found = []
for model, by_reaction in k.items():
    by_key = defaultdict(list)
    for rid, value in by_reaction.items():
        if value > 0:
            by_key[reactions[rid]["canonical_key"]].append(rid)
    found += [(model, a, b) for a, b in (ids for ids in by_key.values() if len(ids) == 2)
              if coeffs(a) == {s: -n for s, n in coeffs(b).items()}]

# %% The thermochemistry entries of these models, by species record
users = {m for m, _, _ in found}
thermo_ids = {m: ids for m, ids in links("thermo").items() if m in users}
wanted = sorted(set().union(*thermo_ids.values()))
entries = {e["id"]: e for n in range(0, len(wanted), 300)
           for e in get_all("/api/thermo/", id__in=",".join(map(str, wanted[n:n + 300])))}
thermo = {m: {entries[t]["species"]: entries[t] for t in ids if t in entries} for m, ids in thermo_ids.items()}

# %% log10 of k_forward / (k_reverse Kc) for each pair: zero when the pair obeys detailed balance
rows = [(math.log10(k[m][a] / k[m][b]) - log_kc(thermo[m], coeffs(a), T) / math.log(10), m,
         reactions[a]["reversible"] or reactions[b]["reversible"])
        for m, a, b in found if all(s in thermo[m] for s in coeffs(a))]
x = np.array([r[0] for r in rows])
print(f"{len(rows)} pairs in {len({r[1] for r in rows})} models give both directions of a reaction")
print(f"  {sum(r[2] for r in rows)} pairs include a reaction record with reversible = true (the flag belongs to the "
      f"reaction record, which all models share)")
print(f"  at 1000 K: within a factor of 1.1 of detailed balance {100 * np.mean(abs(x) < math.log10(1.1)):.1f} %, "
      f"outside a factor of 2 {100 * np.mean(abs(x) > math.log10(2)):.1f} %, outside 10 {100 * np.mean(abs(x) > 1):.1f} %")
for m, n in Counter(r[1] for r in rows).most_common(8):
    sel = np.array([r[0] for r in rows if r[1] == m])
    print(f"  {m:36s} {n:4d} pairs; median |log10| {np.median(abs(sel)):.3f}; outside a factor of 2: {np.sum(abs(sel) > 0.301)}")

# %% Plot the distribution of the deviation, one colour for each of the 5 models with the most pairs
style()
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.axvspan(-math.log10(2), math.log10(2), color="#eaf1f8", zorder=0, lw=0, label="within a factor of 2")
top = [m for m, _ in Counter(r[1] for r in rows).most_common(5)]
groups = [[r[0] for r in rows if r[1] == m] for m in top] + [[r[0] for r in rows if r[1] not in top]]
labels = [f"{m} ({len(g)})" for m, g in zip(top, groups)] + [f"{len(set(r[1] for r in rows)) - 5} other models ({len(groups[-1])})"]
ax.hist([np.clip(g, -3, 3) for g in groups], bins=np.linspace(-3, 3, 61), stacked=True, label=labels,
        color=COLOURS[:5] + ["#a8a8a8"], edgecolor="white", lw=0.2)
ax.set_yscale("log")
ax.set_xlabel("log$_{10}$[k$_{forward}$ / (k$_{reverse}$ K$_c$)] at 1000 K and 1 bar (values beyond ±3 at ±3)")
ax.set_ylabel("Reactions")
ax.set_title(f"{len(rows)} reactions given in both directions, in {len(set(r[1] for r in rows))} models")
ax.legend(loc="upper left", fontsize=7)
save(fig, "uc21_detailed_balance")
