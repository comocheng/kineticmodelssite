"""Use case 22. A kinetic model calculates the reverse rate coefficient of a reversible reaction from
the forward rate coefficient and its own thermochemistry. For the same forward rate, how much do
the reverse rates of the models differ because their thermochemistry differs?"""
# %% Imports
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from chem_tools import R, g_over_rt, log_kc
from prometheus_api import COLOURS, equation, get_all, links, save, style

T = 1000.0
LAYERS = ["H2/O2", "C1", "C2"]

# %% The reaction records of three layers, one direction of each reaction (same canonical_key)
reactions = {}
for r in get_all("/api/reaction/", layer__in=",".join(LAYERS)):
    reactions.setdefault(r["canonical_key"], r)

# %% The thermochemistry entries of each model, by species record (about 20 requests)
entries = {e["id"]: e for e in get_all("/api/thermo/", reference="false")}
thermo = {m: {entries[t]["species"]: entries[t] for t in ids if t in entries and entries[t]["temp_min_1"] <= T <= entries[t]["temp_max_2"]}
          for m, ids in links("thermo").items()}

# %% ln Kc at 1000 K in each model that has all the species. The factor between the reverse rates of the
# middle 80 % of the models is exp(90th - 10th percentile of ln Kc); one wrong entry cannot change it
rows, extreme = [], Counter()
for r in reactions.values():
    coeffs = {s["species"]: s["coeff"] for s in r["stoichiometry_set"]}
    values = {m: log_kc(th, coeffs, T) for m, th in thermo.items() if all(s in th for s in coeffs)}
    if len(values) >= 5:
        v = np.array(list(values.values()))
        rows.append((np.exp(np.percentile(v, 90) - np.percentile(v, 10)), r["layer"], len(v), r))
        far = max(values, key=lambda m: abs(values[m] - np.median(v)))
        if abs(values[far] - np.median(v)) > np.log(100):   # one model a factor of 100 from the median
            extreme[far] += 1

# %% The names that most models use, for the equations
names = Counter()
for m in get_all("/api/kineticmodel/", fields="id,speciesname_set"):
    names.update((n["species"], n["name"]) for n in m["speciesname_set"])
common = {sid: name for (sid, name), _ in reversed(names.most_common())}

# %% Print the result: for each layer, the factor between the largest and the smallest reverse rate
for layer in LAYERS:
    f = np.array([r[0] for r in rows if r[1] == layer])
    print(f"{layer:6s}: {len(f):4d} reactions in 5 or more models; median factor {np.median(f):.2f}; "
          f"factor > 2 for {100 * np.mean(f > 2):4.1f} %, > 10 for {100 * np.mean(f > 10):4.1f} %")
rows.sort(key=lambda r: -r[0])
print("Models that are a factor of 100 or more from the median for the most reactions:",
      ", ".join(f"{m} ({n})" for m, n in extreme.most_common(4)))
print("The 10 largest factors:")
for factor, layer, n, r in rows[:10]:
    print(f"  {factor:10.3g}  {equation(r, common):40s} ({layer}, {n} models)")

# %% The cause: the species whose Gibbs energy at 1000 K differs most between the models (middle 80 %)
in_reactions = {s["species"] for r in reactions.values() for s in r["stoichiometry_set"]}
spread = {}
for sid in in_reactions:
    g = [g_over_rt(th[sid], T) * R * T / 1000 for th in thermo.values() if sid in th]   # kJ/mol
    if len(g) >= 5:
        spread[sid] = np.percentile(g, 90) - np.percentile(g, 10)
worst = sorted(spread, key=spread.get, reverse=True)[:12]
print("Species with the largest spread of G(1000 K), middle 80 % of the models: " +
      ", ".join(f"{common[s]} {spread[s]:.0f} kJ/mol" for s in worst[:6]))

# %% Plot the distribution of the factor for each layer, and the 12 species with the largest spread
style()
fig, (left, right) = plt.subplots(1, 2, figsize=(7.0, 3.6), gridspec_kw={"width_ratios": [1.2, 1], "wspace": 0.45})
for layer, colour in zip(LAYERS, COLOURS):
    f = np.sort([r[0] for r in rows if r[1] == layer])
    left.step(f, 100 * np.arange(1, len(f) + 1) / len(f), where="post", color=colour, label=f"{layer} ({len(f)})")
left.set_xscale("log")
left.set_xlabel("Factor between the reverse rates\n(middle 80 % of the models)")
left.set_ylabel("Reactions with a smaller factor (%)")
left.legend(loc="lower right", title="layer", title_fontsize=8)
right.barh(range(len(worst)), [spread[s] for s in worst], color=COLOURS[3], height=0.65)
right.set_yticks(range(len(worst)), [common[s] for s in worst], fontsize=7.5, fontfamily="monospace")
right.set_ylim(len(worst) - 0.5, -0.5)
right.grid(axis="y", visible=False)
right.tick_params(axis="y", length=0)
right.set_xlabel("Spread of G at 1000 K between the\nmodels, middle 80 % (kJ mol$^{-1}$)")
fig.suptitle("Reverse rate coefficients at 1000 K: the effect of the thermochemistry of the models", x=0.02, ha="left",
             fontsize=10, fontweight="bold")
save(fig, "uc22_reverse_rate_from_thermo")
