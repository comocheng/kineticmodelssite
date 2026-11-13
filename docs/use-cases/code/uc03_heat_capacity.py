"""Use case 3. How much does the heat capacity of the allyl radical (C3H5) differ between the
kinetic models, and from a group-additivity estimate?"""
# %% Imports
import statistics

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import R, cp_over_r, h_kj
from prometheus_api import COLOURS, get, get_all, save, species_id, style

# %% The thermochemistry entries of the models (reference=false leaves out the reference records)
sid = species_id("InChI=1S/C3H5/c1-3-2/h3H,1-2H2")       # allyl, CH2=CH-CH2
entries = get_all("/api/thermo/", species=sid, reference="false")

# %% The group-additivity reference record, and its NASA polynomials (field nasa_thermo)
record = get("/api/thermo-record/", species=sid, provider="group_additivity")["results"][0]
group_additivity = get(f"/api/thermo/{record['nasa_thermo']}/")
print(f"allyl: species record {sid}, {len(entries)} thermochemistry entries of the models; reference record "
      f"{record['id']} ({record['provider']}): enthalpy of formation {record['enthalpy_298'] / 1000:.1f} kJ/mol")

# %% Find the entries whose heat capacity is far from the others, and the models that use them
cp300 = {e["id"]: cp_over_r(e, 300) * R for e in entries}
odd = [e for e in entries if cp300[e["id"]] > 1.5 * statistics.median(cp300.values())]
models = get_all("/api/kineticmodel/", species=sid, fields="model_name,thermocomment_set,speciesname_set")
for e in odd:
    users = [f"{m['model_name']} ({next(n['name'] for n in m['speciesname_set'] if n['species'] == sid)})"
             for m in models if e["id"] in {c["thermo"] for c in m["thermocomment_set"]}]
    e["users"] = "; ".join(users)
    print(f"  entry {e['id']}: Cp(300 K) = {cp300[e['id']]:.1f} J/(mol K) (median of the entries "
          f"{statistics.median(cp300.values()):.1f}), enthalpy of formation {h_kj(e):.1f} kJ/mol, used by {e['users']}")

# %% Plot the heat capacity of each entry
style()
T = np.linspace(300, 2500, 89)
cp = lambda e: [cp_over_r(e, t) * R for t in T]
fig, ax = plt.subplots(figsize=(7.0, 3.6))
for k, e in enumerate(x for x in entries if x not in odd):
    ax.plot(T, cp(e), color="#a8a8a8", lw=0.7, label=f"{len(entries) - len(odd)} entries of the models" if k == 0 else None)
ax.plot(T, cp(group_additivity), color=COLOURS[0], lw=1.8, ls=(0, (4, 2)), label="group additivity")
for e in odd:
    ax.plot(T, cp(e), color=COLOURS[1], lw=1.8, label=e["users"])
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("Heat capacity $C_p$ (J mol$^{-1}$ K$^{-1}$)")
ax.set_title("Allyl radical, C$_3$H$_5$")
ax.legend(loc="lower right")
save(fig, "uc03_heat_capacity")
