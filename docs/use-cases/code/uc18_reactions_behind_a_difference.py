"""Use case 18. Two hydrogen models predict different ignition delays for the same shock-tube
experiments. Which reactions cause the difference? The species records map each reaction of one
model to the same reaction in the other model. The script gives model A the rate expression of
model B for one reaction at a time, and simulates the experiments again in PyTeCK."""
# %% Imports
import tempfile
from pathlib import Path

import cantera as ct
import matplotlib.pyplot as plt
import numpy as np

from prometheus_api import COLOURS, get_text, model_names, model_record, save, style
from pyteck_tools import run_pyteck, species_key

DATASET, A, B = 1733, "CombFlame2014/711-Allen", "CombFlame2017/45-Olm"   # from use case 17

# %% The dataset, and the Cantera file and the species names of each model
chemked = get_text(f"/chemked/dataset/{DATASET}/export/", format="yaml")
ids = {m: model_record(m)["id"] for m in (A, B)}
gas = {m: ct.Solution(yaml=get_text(f"/kineticmodel/{ids[m]}/download/cantera")) for m in (A, B)}
names = {m: model_names(ids[m]) for m in (A, B)}

# %% Each reaction as species records, so that the reactions of the two models can be compared
def as_records(m):
    record = {name: sid for sid, name in names[m].items()}
    side = lambda d: frozenset((record[s], n) for s, n in d.items())
    return [(side(r.reactants), side(r.products)) for r in gas[m].reactions()]

in_A, in_B = as_records(A), as_records(B)
pairs = [(i, in_B.index(r)) for i, r in enumerate(in_A) if in_A.count(r) == 1 and in_B.count(r) == 1]
opposite = sum((r[1], r[0]) in in_B for r in in_A)
print(f"{A}: {len(in_A)} reactions; {B}: {len(in_B)} reactions; {len(pairs)} reactions in both models in the same "
      f"direction; {opposite} in the opposite direction (left out, as the duplicate reactions)")

# %% Simulate the dataset with a Cantera Solution in PyTeCK; returns ln(simulated delay) of each datapoint
key = {m: species_key(chemked, names[m]) for m in (A, B)}

def simulate(solution, m):
    with tempfile.TemporaryDirectory() as folder:
        solution.write_yaml(str(Path(folder, "model.yaml")))
        rows, _, _ = run_pyteck(chemked, Path(folder, "model.yaml").read_text(), key[m])
    return np.log([r[3] for r in rows])

base_A, base_B = simulate(gas[A], A), simulate(gas[B], B)
total = float(np.mean(base_B - base_A))
print(f"dataset {DATASET}: mean ln(tau_B / tau_A) = {total:+.3f} (tau_B / tau_A = {np.exp(total):.2f})")

# %% Give model A the rate expression of model B for one reaction at a time
effect, skipped = {}, []
for i, j in pairs:
    reaction = gas[A].reaction(i)
    if reaction.reaction_type != gas[B].reaction(j).reaction_type:   # for example falloff and Chebyshev
        skipped.append(f"{reaction.equation} ({reaction.reaction_type} / {gas[B].reaction(j).reaction_type})")
        continue
    original = reaction.rate
    reaction.rate = gas[B].reaction(j).rate
    gas[A].modify_reaction(i, reaction)
    effect[gas[B].reaction(j).equation] = float(np.mean(simulate(gas[A], A) - base_A))   # the names of model B
    reaction.rate = original
    gas[A].modify_reaction(i, reaction)
top = sorted(effect, key=lambda e: -abs(effect[e]))[:10]
print(f"  {len(effect)} reactions swapped; {len(skipped)} left out, with different rate types: {'; '.join(skipped) or 'none'}")
for e in top:
    print(f"  {e:32s} {effect[e]:+.3f}  ({100 * effect[e] / total:+5.0f} % of the difference)")
print(f"  sum of all single swaps {sum(effect.values()):+.3f}; the rest comes from the thermochemistry, the collision "
      f"efficiencies, the reactions of one model only, and the interactions between reactions")

# %% Plot the effect of the 10 largest swaps and the total difference
style()
labels = ["total: model B − model A"] + top
values = [total] + [effect[e] for e in top]
fig, ax = plt.subplots(figsize=(7.0, 3.8))
ax.barh(range(len(values)), values, color=[COLOURS[1]] + [COLOURS[0]] * len(top), height=0.65)
ax.axvline(0, color="#1a1a1a", lw=0.8)
ax.set_yticks(range(len(values)), labels, fontsize=7.5, fontfamily="monospace")
ax.set_ylim(len(values) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xlabel("Change of the mean ln(ignition delay) when model A takes the rate of model B")
ax.set_title(f"Dataset {DATASET}: model A = {A}, model B = {B}")
save(fig, "uc18_reactions_behind_a_difference")
