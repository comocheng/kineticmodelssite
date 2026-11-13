"""Use case 7. How does the rate coefficient of CH3 + CH3 (+M) = C2H6 (+M) depend on pressure in
each kinetic model?"""
import math
from collections import Counter, defaultdict

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, get_all, save, species_id, style

CH3, C2H6 = species_id("InChI=1S/CH3/h1H3"), species_id("InChI=1S/C2H6/c1-2/h1-2H3")
want = {CH3: -2, C2H6: 1}
reaction = next(r for r in get_all("/api/reaction/", species=[CH3, C2H6])
                if {s["species"]: s["coeff"] for s in r["stoichiometry_set"]} == want)
# The rate records of the reaction in both directions (C2H6 (+M) = 2 CH3 (+M) is a second reaction record)
records = {k["id"]: k for k in get_all("/api/kinetics/", canonical_key=reaction["canonical_key"])}
models = get_all("/api/kineticmodel/", species=[CH3, C2H6], fields="id,model_name,kineticscomment_set")

# A rate record for one specific collider (for example "(+AR)") gives its collider in specific_collider.
# In a bath gas with a collision efficiency of 1, only the records without a specific collider apply.
per_model, why = defaultdict(list), {}
for m in models:
    mine = [records[c["kinetics"]] for c in m["kineticscomment_set"] if c["kinetics"] in records]
    forward = [r for r in mine if r["reaction"] == reaction["id"]]
    bath = [r for r in forward if not r.get("specific_collider")]
    if bath:
        per_model[m["model_name"]] = bath
    elif forward:
        why[m["model_name"]] = "only a reaction for one specific collider"
    elif mine:
        why[m["model_name"]] = "only the reverse direction, C2H6 (+M) = 2 CH3 (+M)"
    else:
        why[m["model_name"]] = "no rate record for this reaction"

# Check: our rate coefficients against the server's rate_fingerprint (log10 k, SI, 500/1000/1500 K, 1 bar)
agree = sum(all(abs(math.log10(rate_k(r, t)) - f) < 0.002 for t, f in zip((500.0, 1000.0, 1500.0), r["rate_fingerprint"]))
            for r in records.values() if r["rate_fingerprint"] and rate_k(r, 1000.0) > 0)
print(f"reaction record {reaction['id']}: {len(records)} rate records in both directions; {agree} of "
      f"{sum(1 for r in records.values() if r['rate_fingerprint'])} agree with rate_fingerprint")

P = np.logspace(-2, 2, 41) * 1e5   # 0.01 to 100 bar, in Pa
FORM = {"troe": "Troe falloff", "lindemann": "Lindemann falloff", "third_body": "third body",
        "pdep_arrhenius": "PLOG", "multi_pdep_arrhenius": "PLOG", "chebyshev": "Chebyshev",
        "arrhenius": "Arrhenius", "multi_arrhenius": "Arrhenius"}
form = {name: " + ".join(sorted({FORM[r["data"]["type"]] for r in recs})) for name, recs in per_model.items()}
k = {name: [to_cgs(sum(rate_k(r, 1000.0, p) for r in recs), 2) for p in P] for name, recs in per_model.items()}
zero = sorted(name for name, curve in k.items() if max(curve) <= 0)   # the model file gives A = 0
k = {name: curve for name, curve in k.items() if name not in zero}
print(f"{len(per_model)} models give a rate for a bath gas; forms: {dict(Counter(form.values()))}")
print(f"  rate coefficient zero (A = 0 in the model): {', '.join(zero) or 'none'}")
for reason in sorted(set(why.values())):
    print(f"  {reason}: {', '.join(sorted(n for n, w in why.items() if w == reason))}")
for p_bar in (0.1, 1, 10, 100):
    i = int(np.argmin(abs(P - p_bar * 1e5)))
    v = [curve[i] for curve in k.values()]
    print(f"  k(1000 K, {p_bar:5g} bar): {min(v):.2e} to {max(v):.2e} cm3/(mol s), ratio {max(v) / min(v):.1f}")

style()
fig, ax = plt.subplots(figsize=(7.0, 3.9))
order = [f for f, _ in Counter(form.values()).most_common()]
colour = {f: COLOURS[i % len(COLOURS)] for i, f in enumerate(order)}
count = Counter(form[n] for n in k)
for f in reversed(order):   # the largest group first, so the small groups stay visible on top
    for i, name in enumerate(n for n in k if form[n] == f):
        ax.plot(P / 1e5, k[name], color=colour[f], lw=1.6 if f != order[0] else 0.8,
                alpha=1 if f != order[0] else 0.7, label=f"{f} ({count[f]} models)" if i == 0 else None)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Pressure (bar)")
ax.set_ylabel("k at 1000 K (cm$^3$ mol$^{-1}$ s$^{-1}$)")
ax.set_title("CH$_3$ + CH$_3$ (+M) = C$_2$H$_6$ (+M), bath gas with a collision efficiency of 1")
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles[::-1], labels[::-1], title="rate form in the model", loc="lower right", title_fontsize=8)
save(fig, "uc07_pressure_dependence")
