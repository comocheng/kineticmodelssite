"""Use case 15. For which fuels does the database hold both experiments and kinetic models?"""
# %% Imports
import matplotlib.pyplot as plt

from prometheus_api import COLOURS, formula, get, save, species_id, style

FUELS = {"H2": "InChI=1S/H2/h1H", "NH3": "InChI=1S/H3N/h1H3", "CH4": "InChI=1S/CH4/h1H4",
         "C2H6": "InChI=1S/C2H6/c1-2/h1-2H3", "C2H4": "InChI=1S/C2H4/c1-2/h1-2H2", "C2H2": "InChI=1S/C2H2/c1-2/h1-2H",
         "C3H8": "InChI=1S/C3H8/c1-3-2/h3H2,1-2H3", "C3H6": "InChI=1S/C3H6/c1-3-2/h3H,1H2,2H3",
         "CH3OH": "InChI=1S/CH4O/c1-2/h2H,1H3", "C2H5OH": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
         "CH3OCH3": "InChI=1S/C2H6O/c1-3-2/h1-2H3", "n-C4H9OH": "InChI=1S/C4H10O/c1-2-3-4-5/h5H,2-4H2,1H3",
         "n-C7H16": "InChI=1S/C7H16/c1-3-5-7-6-4-2/h3-7H2,1-2H3",
         "iso-C8H18": "InChI=1S/C8H18/c1-7(2)6-8(3,4)5/h7H,6H2,1-5H3", "toluene": "InChI=1S/C7H8/c1-7-5-3-2-4-6-7/h2-6H,1H3"}

# %% One species record selects the experiments (by the mixture) and the models (by the species list)
rows = []
for name, inchi in FUELS.items():
    sid = species_id(inchi)
    n_datasets = get("/api/experiment-dataset/", species=sid, page_size=1)["count"]   # only the count is needed
    n_models = get("/api/kineticmodel/", species=sid, page_size=1, fields="id")["count"]
    rows.append((name, n_datasets, n_models))
    print(f"  {name:10s} species record {sid:6d}: {n_datasets:5d} experimental datasets, {n_models:3d} kinetic models")

# %% Plot the datasets and the models of each fuel side by side
style()
rows.sort(key=lambda r: (r[1], r[2]))
fig, axes = plt.subplots(1, 2, figsize=(7.0, 4.2), sharey=True, gridspec_kw={"wspace": 0.06})
for ax, column, colour, title, xlabel in ((axes[0], 1, COLOURS[0], "Experimental datasets", "Datasets whose mixture contains the species"),
                                          (axes[1], 2, COLOURS[2], "Kinetic models", "Models that contain the species")):
    values = [r[column] for r in rows]
    ax.bar_label(ax.barh(range(len(rows)), values, color=colour, height=0.65), padding=3, fontsize=7.5)
    ax.set_xlim(0, max(values) * 1.18)
    ax.set_title(title, fontsize=9.5)
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
axes[0].set_yticks(range(len(rows)), [name if name[0].islower() or "-" in name else formula(name) for name, _, _ in rows])
fig.suptitle("One species record selects the experiments and the models of a fuel", x=0.12, ha="left",
             fontsize=10, fontweight="bold", y=1.0)
save(fig, "uc15_fuels_experiments_models")
