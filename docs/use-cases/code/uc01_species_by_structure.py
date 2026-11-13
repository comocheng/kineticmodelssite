"""Use case 1. Methoxy (CH3O) and hydroxymethyl (CH2OH) have the same formula. Which species
record is each radical, and which names do the kinetic models use for it?"""
# %% Imports
from collections import Counter

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, species_id, style

# %% Find the species record of each radical from its structure (InChI)
RADICALS = {"methoxy, CH$_3$O": "InChI=1S/CH3O/c1-2/h1H3", "hydroxymethyl, CH$_2$OH": "InChI=1S/CH3O/c1-2/h2H,1H2"}
ids = {radical: species_id(inchi) for radical, inchi in RADICALS.items()}

# %% Count the names that the models use for each species record
names = {}
for radical, sid in ids.items():
    models = get_all("/api/kineticmodel/", species=sid, fields="id,model_name,speciesname_set")
    names[radical] = Counter(n["name"] for m in models for n in m["speciesname_set"] if n["species"] == sid)
    print(f"{radical}: species record {sid}, in {len(models)} models, names: {', '.join(names[radical])}")

# %% Plot the names of each species record
style()
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5))
for ax, (radical, count), colour in zip(axes, names.items(), COLOURS):
    labels, values = zip(*count.most_common())
    ax.bar_label(ax.barh(labels, values, color=colour, height=0.62), padding=3, fontsize=8)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.set_xlim(0, max(values) * 1.15)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"{radical.capitalize()}: species record {ids[radical]}", fontsize=9.5)
    ax.set_xlabel("Models that use this name")
fig.tight_layout(w_pad=3)
save(fig, "uc01_species_by_structure")
