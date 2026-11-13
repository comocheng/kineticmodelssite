"""Use case 1. Methoxy (CH3O) and hydroxymethyl (CH2OH) have the same formula. Which species
record is each radical, and which names do the kinetic models use for it?"""
from collections import Counter

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, species_id, style

# Each species has one species record. The record identifies the species by its structure (InChI).
RADICALS = {"methoxy": "InChI=1S/CH3O/c1-2/h1H3", "hydroxymethyl": "InChI=1S/CH3O/c1-2/h2H,1H2"}

names = {}
for radical, inchi in RADICALS.items():
    sid = species_id(inchi)                       # 1 request: /api/species/?inchi=...
    # The models that contain the species, with the species names of each model (1 request)
    models = get_all("/api/kineticmodel/", species=sid, fields="id,model_name,speciesname_set")
    names[radical] = Counter(n["name"] for m in models for n in m["speciesname_set"] if n["species"] == sid)
    print(f"{radical}: species record {sid}, in {len(models)} models, "
          f"{len(names[radical])} different names: {', '.join(names[radical])}")

style()
fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharex=True)
for ax, (radical, count), colour in zip(axes, names.items(), COLOURS):
    labels, values = zip(*count.most_common())
    bars = ax.barh(labels, values, color=colour)
    ax.bar_label(bars, padding=3)
    ax.invert_yaxis()
    ax.set_title(f"{radical}: one species record", loc="left")
    ax.set_xlabel("Models that use this name")
save(fig, "uc01_species_by_structure")
