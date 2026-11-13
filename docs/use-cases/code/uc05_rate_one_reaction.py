"""Use case 5. Do the kinetic models agree on the rate coefficient of H + O2 = O + OH?"""
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, get, get_all, save, species_id, style

H, O2 = species_id("InChI=1S/H"), species_id("InChI=1S/O2/c1-2", multiplicity=3)
O, OH = species_id("InChI=1S/O", multiplicity=3), species_id("InChI=1S/HO/h1H")
want = {H: -1, O2: -1, O: 1, OH: 1}

# 1. The reaction record: the reactions that contain all four species, then the exact stoichiometry
candidates = get_all("/api/reaction/", species=[H, O2, O, OH])
reaction = next(r for r in candidates if {s["species"]: s["coeff"] for s in r["stoichiometry_set"]} == want)
# 2. All rate records of the reaction, in both directions (1 request)
records = {k["id"]: k for k in get_all("/api/kinetics/", canonical_key=reaction["canonical_key"])}
# 3. The models that contain the four species, with their links to rate records (1 large request)
models = get_all("/api/kineticmodel/", species=[H, O2, O, OH], fields="id,model_name,kineticscomment_set")

per_model = defaultdict(list)
reverse_only = 0
for m in models:
    mine = [records[c["kinetics"]] for c in m["kineticscomment_set"] if c["kinetics"] in records]
    forward = [k for k in mine if k["reaction"] == reaction["id"]]
    if forward:
        per_model[m["model_name"]] = forward
    elif mine:
        reverse_only += 1   # this model gives O + OH = H + O2 only

T = np.linspace(800, 2500, 60)
k = {name: [to_cgs(sum(rate_k(r, t) for r in recs), 2) for t in T] for name, recs in per_model.items()}
k1000 = {name: to_cgs(sum(rate_k(r, 1000.0) for r in recs), 2) for name, recs in per_model.items()}
median = statistics.median(k1000.values())
factors = {name: v / median for name, v in k1000.items()}
print(f"reaction record {reaction['id']} (canonical_key {reaction['canonical_key'][:24]}...)")
print(f"{len(per_model)} models give H + O2 = O + OH with {len({r['id'] for v in per_model.values() for r in v})} "
      f"different rate records; {reverse_only} model{'s' if reverse_only != 1 else ''} "
      f"give{'' if reverse_only != 1 else 's'} only the reverse reaction")
print(f"at 1000 K: median {median:.3e} cm3/(mol s); factors from {min(factors.values()):.2f} to "
      f"{max(factors.values()):.2f}; {sum(0.5 <= f <= 2 for f in factors.values())} models within a factor of 2")

med_curve = np.median(np.array(list(k.values())), axis=0)
worst = max(max(c / m, m / c) for curve in k.values() for c, m in zip(curve, med_curve))
print(f"from {T[0]:.0f} to {T[-1]:.0f} K: the largest factor between a model and the median is {worst:.2f}")

style()
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.fill_between(1000 / T, med_curve / 2, med_curve * 2, color="0.92", label="factor of 2 around the median")
for i, curve in enumerate(k.values()):
    ax.plot(1000 / T, curve, color="0.55", lw=0.6, label=f"{len(k)} models" if i == 0 else None)
ax.plot(1000 / T, med_curve, color=COLOURS[1], lw=2, label="median of the models")
ax.set_yscale("log")
ax.set_xlabel("1000 K / T")
ax.set_ylabel("k (cm$^3$ mol$^{-1}$ s$^{-1}$)")
ax.set_title("H + O$_2$ = O + OH", loc="left")
ax.legend(loc="lower left")
save(fig, "uc05_rate_one_reaction")
