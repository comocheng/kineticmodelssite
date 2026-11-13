"""Use case 3. How much does the heat capacity of the allyl radical (C3H5) differ between the
kinetic models, and from a group-additivity estimate?"""
import statistics

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import R, cp_over_r, h_kj
from prometheus_api import COLOURS, get_all, save, species_id, style

sid = species_id("InChI=1S/C3H5/c1-3-2/h3H,1-2H2")       # allyl, CH2=CH-CH2
entries = get_all("/api/thermo/", species=sid, reference="false")  # the entries of the models
fits = get_all("/api/thermo/", species=sid, reference="true")      # polynomials fitted to reference records
providers = {r["id"]: r["provider"] for r in get_all("/api/thermo-record/", species=sid)}
group_additivity = [f for f in fits if providers.get(f["provider_record"]) == "group_additivity"]
# The models that use each entry, and the name that each model gives to allyl
models = get_all("/api/kineticmodel/", species=sid, fields="id,model_name,thermocomment_set,speciesname_set")
users = {e["id"]: [] for e in entries}
for m in models:
    name = next(n["name"] for n in m["speciesname_set"] if n["species"] == sid)
    for c in m["thermocomment_set"]:
        if c["thermo"] in users:
            users[c["thermo"]].append(f"{m['model_name']} ({name})")

T = np.linspace(300, 2500, 89)
cp300 = {e["id"]: cp_over_r(e, 300) * R for e in entries}
median = statistics.median(cp300.values())
odd = [e for e in entries if cp300[e["id"]] > 1.5 * median]
print(f"allyl: species record {sid}; {len(entries)} thermochemistry entries in {len(models)} models")
print(f"  Cp at 300 K: median of the entries {median:.1f} J/(mol K); "
      f"group additivity {cp_over_r(group_additivity[0], 300) * R:.1f} J/(mol K)")
for e in odd:
    print(f"  entry {e['id']}: Cp(300 K) = {cp300[e['id']]:.1f} J/(mol K), enthalpy of formation "
          f"{h_kj(e):.1f} kJ/mol, used by {', '.join(users[e['id']])}")

style()
fig, ax = plt.subplots(figsize=(7.0, 3.6))
for k, e in enumerate(x for x in entries if x not in odd):
    ax.plot(T, [cp_over_r(e, t) * R for t in T], color="#a8a8a8", lw=0.7,
            label=f"{len(entries) - len(odd)} entries of the models" if k == 0 else None)
for f in group_additivity:
    ax.plot(T, [cp_over_r(f, t) * R for t in T], color=COLOURS[0], lw=1.8, ls=(0, (4, 2)), label="group additivity")
for e in odd:
    ax.plot(T, [cp_over_r(e, t) * R for t in T], color=COLOURS[1], lw=1.8, label="; ".join(users[e["id"]]))
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("Heat capacity $C_p$ (J mol$^{-1}$ K$^{-1}$)")
ax.set_title("Allyl radical, C$_3$H$_5$")
ax.legend(loc="lower right")
save(fig, "uc03_heat_capacity")
