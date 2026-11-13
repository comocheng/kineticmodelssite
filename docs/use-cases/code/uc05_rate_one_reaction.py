"""Use case 5. Do the kinetic models agree on the rate coefficient of H + O2 = O + OH?"""
# %% Imports
import matplotlib.pyplot as plt
import numpy as np

from chem_tools import rate_k, to_cgs
from prometheus_api import COLOURS, find_reaction, get_all, links, save, species_id, style, temperature_axis

# %% The species records (O2 and O have a singlet and a triplet record: take the triplet)
H, OH = species_id("InChI=1S/H"), species_id("InChI=1S/HO/h1H")
O2, O = species_id("InChI=1S/O2/c1-2", multiplicity=3), species_id("InChI=1S/O", multiplicity=3)

# %% The reaction record and all its rate records (in both directions)
reaction = find_reaction([H, O2], [O, OH])
records = {k["id"]: k for k in get_all("/api/kinetics/", canonical_key=reaction["canonical_key"])}

# %% The rate records that each model uses in this direction
per_model = {model: [records[i] for i in ids if i in records and records[i]["reaction"] == reaction["id"]]
             for model, ids in links("kinetics", [H, O2, O, OH]).items()}
per_model = {model: recs for model, recs in per_model.items() if recs}

# %% The rate coefficient of each model from 800 to 2500 K, and the median of the models
T = np.linspace(800, 2500, 60)
k = np.array([[to_cgs(sum(rate_k(r, t) for r in recs), 2) for t in T] for recs in per_model.values()])
median = np.median(k, axis=0)
factor = np.max(np.maximum(k / median, median / k))
print(f"reaction record {reaction['id']}: {len(per_model)} models use "
      f"{len({r['id'] for recs in per_model.values() for r in recs})} different rate records")
print(f"median at 1000 K: {np.interp(1000, T, median):.3e} cm3/(mol s); largest factor between a model and the "
      f"median, 800 to 2500 K: {factor:.2f}")

# %% Plot the rate coefficients of the models against 1000/T
style()
fig, ax = plt.subplots(figsize=(7.0, 3.9))
ax.fill_between(1000 / T, median / 2, median * 2, color="#eaf1f8", lw=0, label="factor of 2 around the median")
ax.plot(1000 / T, k.T, color="#8f8f8f", lw=0.5, alpha=0.8)
ax.plot([], [], color="#8f8f8f", lw=0.5, label=f"{len(k)} models")
ax.plot(1000 / T, median, color=COLOURS[1], lw=2, label="median of the models")
ax.set_yscale("log")
ax.set_xlabel("1000 K / T")
ax.set_ylabel("k (cm$^3$ mol$^{-1}$ s$^{-1}$)")
temperature_axis(ax, [2500, 2000, 1500, 1200, 1000, 900, 800])
ax.set_title("H + O$_2$ = O + OH", pad=30)
ax.legend(loc="lower left")
save(fig, "uc05_rate_one_reaction")
