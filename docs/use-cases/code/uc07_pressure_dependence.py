"""Use case 7. How does the rate coefficient of CH3 + CH3 (+M) = C2H6 (+M) depend on pressure in
each kinetic model?"""
# %% Imports
import math
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, find_reaction, get_all, links, save, species_id, style

# %% The reaction record, and its rate records in both directions
CH3, C2H6 = species_id("InChI=1S/CH3/h1H3"), species_id("InChI=1S/C2H6/c1-2/h1-2H3")
reaction = find_reaction([CH3, CH3], [C2H6])
records = {k["id"]: k for k in get_all("/api/kinetics/", canonical_key=reaction["canonical_key"])}

# %% Check our rate coefficients against the server's rate_fingerprint (log10 k in SI at 500, 1000, 1500 K)
check = [r for r in records.values() if r["rate_fingerprint"] and rate_k(r, 1000.0) > 0]
agree = sum(all(abs(math.log10(rate_k(r, t)) - f) < 0.002 for t, f in zip((500.0, 1000.0, 1500.0), r["rate_fingerprint"]))
            for r in check)
print(f"reaction record {reaction['id']}: {len(records)} rate records; {agree} of {len(check)} agree with rate_fingerprint")

# %% For each model: the rate records in this direction for a bath gas (no specific_collider)
per_model, why = {}, {}
for model, ids in links("kinetics", [CH3, C2H6]).items():
    mine = [records[i] for i in ids if i in records]
    forward = [r for r in mine if r["reaction"] == reaction["id"]]
    bath = [r for r in forward if not r["specific_collider"]]
    if bath:
        per_model[model] = bath
    else:
        why[model] = ("only a reaction for one specific collider" if forward else
                      "only the reverse direction, C2H6 (+M) = 2 CH3 (+M)" if mine else "no rate record for this reaction")

# %% The rate coefficient at 1000 K from 0.01 to 100 bar, and the rate form of each model
FORM = {"troe": "Troe falloff", "lindemann": "Lindemann falloff", "third_body": "third body",
        "pdep_arrhenius": "PLOG", "multi_pdep_arrhenius": "PLOG", "chebyshev": "Chebyshev",
        "arrhenius": "Arrhenius", "multi_arrhenius": "Arrhenius"}
P = np.logspace(-2, 2, 41) * 1e5   # Pa
k = {m: [to_cgs(sum(rate_k(r, 1000.0, p) for r in recs), 2) for p in P] for m, recs in per_model.items()}
zero = sorted(m for m, curve in k.items() if max(curve) <= 0)   # the model file gives A = 0
k = {m: curve for m, curve in k.items() if m not in zero}
form = {m: " + ".join(sorted({FORM[r["data"]["type"]] for r in per_model[m]})) for m in k}

# %% Print the result
print(f"{len(per_model)} models give a rate for a bath gas; forms: {dict(Counter(form.values()))}")
print(f"  rate coefficient zero (A = 0 in the model): {', '.join(zero) or 'none'}")
for reason in sorted(set(why.values())):
    print(f"  {reason}: {', '.join(sorted(m for m, w in why.items() if w == reason))}")
for p_bar in (0.1, 1, 10, 100):
    v = [curve[int(np.argmin(abs(P - p_bar * 1e5)))] for curve in k.values()]
    print(f"  k(1000 K, {p_bar:5g} bar): {min(v):.2e} to {max(v):.2e} cm3/(mol s), ratio {max(v) / min(v):.1f}")

# %% Plot k against pressure, one colour for each rate form
style()
fig, ax = plt.subplots(figsize=(7.0, 3.9))
count = Counter(form.values())
order = [f for f, _ in count.most_common()]
for f, colour in reversed(list(zip(order, COLOURS))):   # the largest group first, so the small groups stay on top
    common = f == order[0]
    for i, m in enumerate(m for m in k if form[m] == f):
        ax.plot(P / 1e5, k[m], color=colour, lw=0.8 if common else 1.6, alpha=0.7 if common else 1,
                label=f"{f} ({count[f]} models)" if i == 0 else None)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Pressure (bar)")
ax.set_ylabel("k at 1000 K (cm$^3$ mol$^{-1}$ s$^{-1}$)")
ax.set_title("CH$_3$ + CH$_3$ (+M) = C$_2$H$_6$ (+M), bath gas with a collision efficiency of 1")
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles[::-1], labels[::-1], title="rate form in the model", loc="lower right", title_fontsize=8)
save(fig, "uc07_pressure_dependence")
