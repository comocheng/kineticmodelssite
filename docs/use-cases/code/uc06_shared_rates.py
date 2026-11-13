"""Use case 6. For CH4 + OH = CH3 + H2O, which rate expressions do the kinetic models share?"""
from collections import defaultdict

import matplotlib.pyplot as plt

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, get_all, save, species_id, style

CH4, OH = species_id("InChI=1S/CH4/h1H4"), species_id("InChI=1S/HO/h1H")
CH3, H2O = species_id("InChI=1S/CH3/h1H3"), species_id("InChI=1S/H2O/h1H2")
want = {CH4: -1, OH: -1, CH3: 1, H2O: 1}
reaction = next(r for r in get_all("/api/reaction/", species=[CH4, OH, CH3, H2O])
                if {s["species"]: s["coeff"] for s in r["stoichiometry_set"]} == want)
# The rate records of this reaction record (this direction only)
records = {k["id"]: k for k in get_all("/api/kinetics/", reaction=reaction["id"])}
models = get_all("/api/kineticmodel/", species=[CH4, OH, CH3, H2O], fields="id,model_name,kineticscomment_set")

# A rate record is stored once. Each model links to the rate record that it uses.
users = defaultdict(list)
for m in models:
    for c in m["kineticscomment_set"]:
        if c["kinetics"] in records:
            users[c["kinetics"]].append(m["model_name"])
ranked = sorted(users.items(), key=lambda kv: -len(kv[1]))
print(f"reaction record {reaction['id']}: {sum(len(v) for v in users.values())} model links to "
      f"{len(users)} different rate records")
for rid, names in ranked[:6]:
    d = records[rid]["data"]
    k1000 = to_cgs(rate_k(records[rid], 1000.0), 2)
    form = (f"A = {to_cgs(d['a_si'], 2):.3g} cm3/(mol s), n = {d['n']:.3g}, Ea = {d['e_si'] / 1000:.2f} kJ/mol"
            if d["type"] == "arrhenius" else d["type"])
    print(f"  rate record {rid}: {len(names):2d} models | {form} | k(1000 K) = {k1000:.3e} cm3/(mol s) | "
          f"for example {', '.join(names[:3])}")

style()
fig, ax = plt.subplots(figsize=(7, 3.8))
labels = []
for rid, names in ranked:
    d = records[rid]["data"]
    # one set of units for every label: A in cm3/(mol s), Ea in kJ/mol
    labels.append(f"A = {to_cgs(d['a_si'], 2):.3g}, n = {d['n']:.3g}, Ea = {d['e_si'] / 1000:.2f} kJ/mol"
                  if d["type"] == "arrhenius" else d["type"])
bars = ax.barh(range(len(ranked)), [len(v) for _, v in ranked], color=COLOURS[0])
ax.bar_label(bars, padding=3, fontsize=8)
ax.set_yticks(range(len(ranked)), labels, fontsize=7)
ax.invert_yaxis()
ax.set_xlabel("Models that use this rate record")
ax.set_title("CH$_4$ + OH = CH$_3$ + H$_2$O: one bar per rate record", loc="left")
save(fig, "uc06_shared_rates")
