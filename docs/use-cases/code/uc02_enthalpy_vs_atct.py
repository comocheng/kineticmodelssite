"""Use case 2. Which kinetic models use an enthalpy of formation that differs from the
Active Thermochemical Tables (ATcT), and by how much?"""
# %% Imports
import matplotlib.pyplot as plt

from chem_tools import h_kj
from prometheus_api import COLOURS, formula, get, get_all, links, save, species_id, style

SPECIES = {"CH3O": "InChI=1S/CH3O/c1-2/h1H3", "CH2OH": "InChI=1S/CH3O/c1-2/h2H,1H2",
           "CH2CHO": "InChI=1S/C2H3O/c1-2-3/h2H,1H2", "HCO": "InChI=1S/CHO/c1-2/h1H",
           "HO2": "InChI=1S/HO2/c1-2/h1H", "OH": "InChI=1S/HO/h1H"}
KCAL = 4.184  # kJ/mol

# %% For each species: the entries of the models, the entry that each model uses, and ATcT
diff = {}
for name, inchi in SPECIES.items():
    sid = species_id(inchi)
    entries = {e["id"]: e for e in get_all("/api/thermo/", species=sid, reference="false")}
    used = [t for ts in links("thermo", [sid]).values() for t in ts if t in entries]   # one entry per model
    atct = get("/api/thermo-record/", provider="atct", species=sid)["results"][0]
    ref = atct["enthalpy_298"] / 1000                                                    # J/mol to kJ/mol
    diff[name] = [h_kj(entries[t]) - ref for t in used]
    print(f"{name:7s} ATcT {ref:8.2f} ± {atct['uncertainty_298'] / 1000:.2f} kJ/mol | {len(used)} models, "
          f"{len(set(used))} entries | {sum(abs(d) > KCAL for d in diff[name])} models off by more than 1 kcal/mol")

# %% Plot each model value minus ATcT
style()
fig, ax = plt.subplots(figsize=(7.0, 3.3))
ax.axvspan(-KCAL, KCAL, color="#eaf1f8", zorder=0, lw=0, label="within 1 kcal/mol of ATcT")
for i, d in enumerate(diff.values()):
    y = [i + 0.28 * ((k * 0.618) % 1 - 0.5) for k in range(len(d))]                 # spread the dots a little
    ax.scatter(d, y, s=15, c=[COLOURS[1] if abs(x) > KCAL else COLOURS[0] for x in d], alpha=0.8,
               edgecolors="white", linewidths=0.3, zorder=3)
ax.axvline(0, color="#1a1a1a", lw=0.9, zorder=2)
ax.set_yticks(range(len(diff)), [formula(n) for n in diff])
ax.set_ylim(len(diff) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.set_xlabel("Enthalpy of formation at 298.15 K, model minus ATcT (kJ mol$^{-1}$)")
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0))
save(fig, "uc02_enthalpy_vs_atct")
