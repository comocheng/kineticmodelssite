"""Use case 9. Which kinetic models contain both NH3 and H2, and how large are they?"""
# %% Imports
import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, species_id, style

# %% A repeated species parameter selects the models that contain every species given (1 request)
NH3, H2 = species_id("InChI=1S/H3N/h1H3"), species_id("InChI=1S/H2/h1H")
both = {m["id"]: m["model_name"] for m in get_all("/api/kineticmodel/", species=[NH3, H2], fields="id,model_name")}

# %% The size of every model: the number of species in its species list (1 request)
models = get_all("/api/kineticmodel/", fields="id,model_name,speciesname_set")
size = {m["id"]: len({n["species"] for n in m["speciesname_set"]}) for m in models}
print(f"{len(both)} of {len(models)} models contain both NH3 and H2:")
for mid, name in sorted(both.items(), key=lambda kv: size[kv[0]]):
    print(f"  {name:28s} model {mid:4d}: {size[mid]:5d} species")

# %% Plot the size of every model, from the smallest to the largest
style()
order = sorted(size, key=size.get)
fig, ax = plt.subplots(figsize=(7.0, 3.4))
ax.bar(range(len(order)), [size[m] for m in order], width=0.8, color=[COLOURS[1] if m in both else "#c9c9c9" for m in order])
for x, m in enumerate(order):
    if m in both:
        ax.annotate(both[m], (x, size[m]), xytext=(0, 4), textcoords="offset points", rotation=90,
                    ha="center", va="bottom", fontsize=7.5, color=COLOURS[1])
ax.set_yscale("log")
ax.set_xticks([])
ax.grid(axis="x", visible=False)
ax.set_xlim(-1, len(order))
ax.set_ylim(top=max(size.values()) * 6)
ax.set_xlabel(f"The {len(models)} models of the database, from the smallest to the largest")
ax.set_ylabel("Species in the model")
ax.set_title("The models that contain both NH$_3$ and H$_2$ (vermilion)")
save(fig, "uc09_models_with_species")
