"""Use case 6. For CH4 + OH = CH3 + H2O, which rate expressions do the kinetic models share?"""
# %% Imports
import matplotlib.pyplot as plt

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, find_reaction, get_all, links, save, species_id, style

# %% The reaction record and its rate records (this direction only)
CH4, OH = species_id("InChI=1S/CH4/h1H4"), species_id("InChI=1S/HO/h1H")
CH3, H2O = species_id("InChI=1S/CH3/h1H3"), species_id("InChI=1S/H2O/h1H2")
reaction = find_reaction([CH4, OH], [CH3, H2O])
records = {k["id"]: k for k in get_all("/api/kinetics/", reaction=reaction["id"])}

# %% A rate record is stored once, and each model links to the rate record that it uses
model_links = links("kinetics", [CH4, OH, CH3, H2O])
users = {rid: [m for m, ids in model_links.items() if rid in ids] for rid in records}
ranked = sorted(((rid, ms) for rid, ms in users.items() if ms), key=lambda kv: -len(kv[1]))

# %% Print the parameters of the most used rate records (A in cm3/(mol s), Ea in kJ/mol)
def label(record):
    d = record["data"]
    if d["type"] != "arrhenius":
        return d["type"]
    return f"A = {to_cgs(d['a_si'], 2):.3g}, n = {d['n']:.3g}, Ea = {d['e_si'] / 1000:.2f} kJ/mol"

print(f"reaction record {reaction['id']}: {sum(len(v) for _, v in ranked)} model links to {len(ranked)} rate records")
for rid, models in ranked[:6]:
    print(f"  rate record {rid}: {len(models):2d} models | {label(records[rid])} | k(1000 K) = "
          f"{to_cgs(rate_k(records[rid], 1000.0), 2):.3e} cm3/(mol s) | for example {', '.join(models[:3])}")

# %% Plot the number of models that use each rate record
style()
fig, ax = plt.subplots(figsize=(7.0, 0.26 * len(ranked) + 1.0))
bars = ax.barh(range(len(ranked)), [len(v) for _, v in ranked], color=COLOURS[0], height=0.65)
ax.bar_label(bars, padding=3, fontsize=8)
ax.set_yticks(range(len(ranked)), [label(records[rid]) for rid, _ in ranked], fontsize=7.5)
ax.set_ylim(len(ranked) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xlabel("Models that use this rate record")
ax.set_title("CH$_4$ + OH = CH$_3$ + H$_2$O: one bar for each rate record")
save(fig, "uc06_shared_rates")
