"""Use case 8. In the model NitrogenGlarborg2018, which reactions consume NH2, and which of them
are the fastest at 1000 K?"""
import matplotlib.pyplot as plt

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, get, get_all, save, species_id, style

model = next(m for m in get_all("/api/kineticmodel/", search="NitrogenGlarborg2018", fields="id,model_name")
             if m["model_name"] == "NitrogenGlarborg2018")
NH2 = species_id("InChI=1S/H2N/h1H2")
# The rate records of this model for the reactions that contain NH2 (1 request), and their reactions
records = get_all("/api/kinetics/", kinetic_model=model["id"], species=NH2)
reactions = {r["id"]: r for r in get_all("/api/reaction/", id__in=",".join(str(k["reaction"]) for k in records))}
# The names that this model uses for its species, for the equations
names = {n["species"]: n["name"] for n in get(f"/api/kineticmodel/{model['id']}/", fields="speciesname_set")["speciesname_set"]}


def equation(rxn):
    side = lambda sign: " + ".join(
        (f"{int(abs(s['coeff']))} " if abs(s["coeff"]) > 1 else "") + names.get(s["species"], str(s["species"]))
        for s in rxn["stoichiometry_set"] if s["coeff"] * sign > 0)
    return f"{side(-1)} = {side(1)}"


rows = []
for k in records:
    rxn = reactions[k["reaction"]]
    coeff = {s["species"]: s["coeff"] for s in rxn["stoichiometry_set"]}
    order = -sum(c for c in coeff.values() if c < 0)
    if coeff.get(NH2, 0) < 0 and order == 2 and not k.get("specific_collider"):   # NH2 + X, bimolecular
        rows.append((to_cgs(rate_k(k, 1000.0), 2), equation(rxn), k["data"]["type"]))
rows.sort(reverse=True)
print(f"model {model['id']} {model['model_name']}: {len(records)} rate records contain NH2; "
      f"{len(rows)} are bimolecular reactions that consume NH2")
for v, eq, t in rows[:10]:
    print(f"  {v:10.3e} cm3/(mol s)  {eq}  ({t})")

style()
top = rows[:20]
fig, ax = plt.subplots(figsize=(7, 5))
ax.barh(range(len(top)), [v for v, _, _ in top], color=COLOURS[2])
ax.set_yticks(range(len(top)), [eq for _, eq, _ in top], fontsize=8)
ax.invert_yaxis()
ax.set_xscale("log")
ax.xaxis.set_minor_formatter(plt.NullFormatter())   # label the powers of ten only
ax.set_xlabel("k at 1000 K and 1 bar (cm$^3$ mol$^{-1}$ s$^{-1}$)")
ax.set_title(f"The 20 fastest reactions of NH$_2$ + X in {model['model_name']}", loc="left", fontsize=10)
save(fig, "uc08_reactions_of_species")
