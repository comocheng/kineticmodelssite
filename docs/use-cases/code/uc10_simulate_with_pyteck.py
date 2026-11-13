"""Use case 10. Download one experimental dataset and one kinetic model, and simulate the experiments
with PyTeCK: how well does the model reproduce the measured ignition delays?"""
# %% Imports
import statistics

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get, get_text, model_names, model_record, paper, save, style, temperature_axis
from pyteck_tools import run_pyteck, species_key

# %% The dataset (hydrogen/Cheng_1984: H2/O2/Ar in a shock tube) and the model
dataset = get("/api/experiment-dataset/1616/", fields="id,chemked_file_path,reference_doi")
model = model_record("CombFlame2015/3755-Konnov")

# %% Download the ChemKED file and the Cantera file
chemked = get_text(f"/chemked/dataset/{dataset['id']}/export/", format="yaml")
cantera = get_text(f"/kineticmodel/{model['id']}/download/cantera")

# %% PyTeCK's species key: the name in the model of each mixture component, by the InChI
key = species_key(chemked, model_names(model["id"]))
print(f"dataset {dataset['id']} ({dataset['chemked_file_path']}, doi {dataset['reference_doi']})")
print(f"model {model['id']} {model['model_name']}; species key from the species records: {key}")

# %% Simulate each datapoint with PyTeCK
rows, E, sigma = run_pyteck(chemked, cantera, key)
ratio = [sim / exp for _, _, exp, sim in rows]
print(f"{len(rows)} datapoints, {min(r[0] for r in rows):.0f} to {max(r[0] for r in rows):.0f} K, "
      f"{min(r[1] for r in rows):.1f} to {max(r[1] for r in rows):.1f} bar")
print(f"PyTeCK error function E = {E:.2f} (sigma of ln(delay) {sigma:.3f}); simulated / measured "
      f"ignition delay: median {statistics.median(ratio):.2f}, from {min(ratio):.2f} to {max(ratio):.2f}")

# %% Plot the measured and the simulated ignition delays against 1000/T
style()
fig, ax = plt.subplots(figsize=(7.0, 3.9))
x = [1000 / r[0] for r in rows]
ax.plot(x, [r[2] * 1e6 for r in rows], "o", color="#1a1a1a", ms=5, mec="white", mew=0.4, label="measured")
ax.plot(x, [r[3] * 1e6 for r in rows], "s", color=COLOURS[1], ms=4.5, mec="white", mew=0.4,
        label=f"simulated with PyTeCK, {model['model_name']}")
ax.set_yscale("log")
ax.set_xlabel("1000 K / T")
ax.set_ylabel("Ignition delay (µs)")
temperature_axis(ax, [1600, 1400, 1200, 1100, 1000])
ax.set_title(f"H$_2$/O$_2$/Ar in a shock tube, {paper(dataset)} (dataset {dataset['id']}): E = {E:.2f}", pad=30)
ax.legend(loc="upper left")
save(fig, "uc10_simulate_with_pyteck")
