"""Use case 2. Which kinetic models use an enthalpy of formation that differs from the
Active Thermochemical Tables (ATcT), and by how much?"""
import matplotlib.pyplot as plt

from chem_tools import h_kj
from prometheus_api import COLOURS, formula, get, get_all, save, species_id, style

SPECIES = {"CH3O": "InChI=1S/CH3O/c1-2/h1H3", "CH2OH": "InChI=1S/CH3O/c1-2/h2H,1H2",
           "CH2CHO": "InChI=1S/C2H3O/c1-2-3/h2H,1H2", "HCO": "InChI=1S/CHO/c1-2/h1H",
           "HO2": "InChI=1S/HO2/c1-2/h1H", "OH": "InChI=1S/HO/h1H"}
KCAL = 4.184  # kJ/mol

rows = {}
for name, inchi in SPECIES.items():
    sid = species_id(inchi)
    # The thermochemistry entries of the models for this species (reference=false: model entries only)
    entries = {e["id"]: e for e in get_all("/api/thermo/", species=sid, reference="false")}
    # Each model links to one of these entries through its thermocomment_set
    models = get_all("/api/kineticmodel/", species=sid, fields="id,model_name,thermocomment_set")
    atct = get("/api/thermo-record/", provider="atct", species=sid)["results"]
    ref = atct[0]["enthalpy_298"] / 1000  # J/mol to kJ/mol
    values = [h_kj(entries[c["thermo"]]) for m in models for c in m["thermocomment_set"] if c["thermo"] in entries]
    off = sum(abs(v - ref) > KCAL for v in values)
    rows[name] = (values, ref, atct[0]["uncertainty_298"] / 1000)
    print(f"{name:7s} ATcT {ref:8.2f} ± {atct[0]['uncertainty_298'] / 1000:.2f} kJ/mol | {len(values)} models, "
          f"{len({c['thermo'] for m in models for c in m['thermocomment_set'] if c['thermo'] in entries})} entries, "
          f"range {min(values):.1f} to {max(values):.1f} kJ/mol | {off} models off by more than 1 kcal/mol")

style()
from matplotlib.lines import Line2D
fig, ax = plt.subplots(figsize=(7.0, 3.3))
ax.axvspan(-KCAL, KCAL, color="#eaf1f8", zorder=0, lw=0)
for i, (name, (values, ref, unc)) in enumerate(rows.items()):
    d = [v - ref for v in values]
    colours = [COLOURS[1] if abs(x) > KCAL else COLOURS[0] for x in d]
    jitter = [i + 0.28 * ((k * 0.618) % 1 - 0.5) for k in range(len(d))]
    ax.scatter(d, jitter, s=15, c=colours, alpha=0.8, edgecolors="white", linewidths=0.3, zorder=3)
ax.axvline(0, color="#1a1a1a", lw=0.9, zorder=2)
ax.set_yticks(range(len(rows)), [formula(n) for n in rows])
ax.set_ylim(len(rows) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xlabel("Enthalpy of formation at 298.15 K, model minus ATcT (kJ mol$^{-1}$)")
ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
handles = [Line2D([], [], ls="", marker="o", color=COLOURS[0], label="within 1 kcal/mol of ATcT (shaded band)"),
           Line2D([], [], ls="", marker="o", color=COLOURS[1], label="more than 1 kcal/mol from ATcT")]
ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.2)
save(fig, "uc02_enthalpy_vs_atct")
