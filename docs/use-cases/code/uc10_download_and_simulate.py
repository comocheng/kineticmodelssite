"""Use case 10. Download a kinetic model in Cantera format and calculate the ignition delay of a
stoichiometric methane-air mixture at 10 atm."""
import warnings

import cantera as ct
import matplotlib.pyplot as plt
import numpy as np

from prometheus_api import COLOURS, get, get_all, get_text, save, species_id, style

model = next(m for m in get_all("/api/kineticmodel/", search="GRI-mech-3.0", fields="id,model_name")
             if m["model_name"] == "GRI-mech-3.0")
text = get_text(f"/kineticmodel/{model['id']}/download/cantera")     # Cantera YAML, 1 request
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    gas = ct.Solution(yaml=text)
print(f"model {model['id']} {model['model_name']}: {gas.n_species} species, {gas.n_reactions} reactions; "
      f"Cantera gave {len(caught)} warnings on loading")

# The name that this model uses for each species: find it from the species record, not from a guess
names = {n["species"]: n["name"] for n in get(f"/api/kineticmodel/{model['id']}/", fields="speciesname_set")["speciesname_set"]}
CH4 = names[species_id("InChI=1S/CH4/h1H4")]
O2 = names[species_id("InChI=1S/O2/c1-2", multiplicity=3)]
N2 = names[species_id("InChI=1S/N2/c1-2")]


def ignition(T0, P=10 * ct.one_atm):
    gas.TPX = T0, P, {CH4: 1.0, O2: 2.0, N2: 7.52}
    reactor = ct.IdealGasConstPressureReactor(gas)
    net = ct.ReactorNet([reactor])
    t, T = [0.0], [T0]
    while net.time < 0.2 and reactor.T < T0 + 1500:
        net.step()
        t.append(net.time)
        T.append(reactor.T)
    t, T = np.array(t), np.array(T)
    return t, T, t[np.argmax(np.gradient(T, t))]   # ignition delay: time of the largest dT/dt


style()
fig, ax = plt.subplots(figsize=(6.5, 3.8))
for T0, colour in zip((1300, 1200, 1100), COLOURS):
    t, T, tau = ignition(T0)
    print(f"  T0 = {T0} K, 10 atm, phi = 1: ignition delay {tau * 1e3:.3f} ms")
    ax.plot(t * 1e3, T, color=colour, label=f"$T_0$ = {T0} K: {tau * 1e3:.2f} ms")
    ax.axvline(tau * 1e3, color=colour, lw=0.8, ls=":")
ax.set_xscale("log")
ax.set_xlim(1e-3, None)
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Temperature (K)")
ax.set_title(f"CH$_4$-air, 10 atm, constant pressure; model {model['model_name']}", loc="left", fontsize=10)
ax.legend(title="ignition delay (dotted line)", fontsize=8)
save(fig, "uc10_download_and_simulate")
