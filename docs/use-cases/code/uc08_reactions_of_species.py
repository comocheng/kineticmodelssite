"""Use case 8. In the model NitrogenGlarborg2018, which reactions consume NH2, and which of them
are the fastest at 1000 K?"""
# %% Imports
import matplotlib.pyplot as plt

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, equation, get_all, model_names, model_record, save, species_id, style

# %% The model, and its rate records for the reactions that contain NH2 (1 request)
model = model_record("NitrogenGlarborg2018")
NH2 = species_id("InChI=1S/H2N/h1H2")
records = get_all("/api/kinetics/", kinetic_model=model["id"], species=NH2)

# %% The reaction records of these rate records, and the species names of the model
reactions = {r["id"]: r for r in get_all("/api/reaction/", id__in=",".join(str(k["reaction"]) for k in records))}
names = model_names(model["id"])

# %% Keep the bimolecular reactions NH2 + X, and calculate k at 1000 K
rows = []
for k in records:
    coeff = {s["species"]: s["coeff"] for s in reactions[k["reaction"]]["stoichiometry_set"]}
    if coeff.get(NH2, 0) < 0 and -sum(c for c in coeff.values() if c < 0) == 2 and not k["specific_collider"]:
        rows.append((to_cgs(rate_k(k, 1000.0), 2), equation(reactions[k["reaction"]], names), k["data"]["type"]))
rows.sort(reverse=True)
print(f"model {model['id']} {model['model_name']}: {len(records)} rate records contain NH2; "
      f"{len(rows)} are bimolecular reactions that consume NH2")
for v, eq, t in rows[:10]:
    print(f"  {v:10.3e} cm3/(mol s)  {eq}  ({t})")

# %% Plot the 20 fastest reactions
style()
top = rows[:20]
fig, ax = plt.subplots(figsize=(7.0, 5.0))
ax.barh(range(len(top)), [v for v, _, _ in top], color=COLOURS[2], height=0.65)
ax.set_yticks(range(len(top)), [eq for _, eq, _ in top], fontfamily="monospace", fontsize=7.5)
ax.set_ylim(len(top) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xscale("log")
ax.set_xlabel("k at 1000 K and 1 bar (cm$^3$ mol$^{-1}$ s$^{-1}$)")
ax.set_title(f"The 20 fastest reactions NH$_2$ + X in {model['model_name']}")
save(fig, "uc08_reactions_of_species")
