"""Use case 18. Which kinetic models share most of their rate expressions and their thermochemistry,
that is, which models were built from the same parts?"""
# %% Imports
import matplotlib.pyplot as plt
import numpy as np
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from prometheus_api import links, save, style

# %% The rate records and the thermochemistry entries that each model links to (2 large requests)
rates, thermo = links("kinetics"), links("thermo")
models = sorted(m for m in rates if rates[m] and thermo.get(m))

# %% Jaccard similarity: the records that two models share, divided by the records of either model
def jaccard(sets):
    return np.array([[len(sets[a] & sets[b]) / len(sets[a] | sets[b]) for b in models] for a in models])

J_rate, J_thermo = jaccard(rates), jaccard(thermo)

# %% Print the pairs of models that share the most rate records
pairs = sorted(((J_rate[i, j], J_thermo[i, j], models[i], models[j]) for i in range(len(models))
                for j in range(i + 1, len(models))), reverse=True)
print(f"{len(models)} models, {len(pairs)} pairs; {sum(p[0] > 0.5 for p in pairs)} pairs share more than half "
      f"of their rate records, {sum(p[0] < 0.01 for p in pairs)} pairs less than 1 %")
for jr, jt, a, b in pairs[:8]:
    print(f"  rate records {jr:4.2f}, thermochemistry {jt:4.2f}: {a} and {b}")

# %% Keep the models that share at least 30 % of their rate records with another model, and cluster them
related = [i for i in range(len(models)) if max(np.delete(J_rate[i], i)) >= 0.3]
print(f"{len(related)} models share at least 30 % of their rate records with another model")
J = J_rate[np.ix_(related, related)]
order = [related[i] for i in leaves_list(linkage(squareform(1 - J, checks=False), "average"))]

# %% Plot both similarities in one matrix: rate records below the diagonal, thermochemistry above
style()
M = np.where(np.tri(len(models), k=-1, dtype=bool), J_rate, J_thermo)
np.fill_diagonal(M, np.nan)
fig, ax = plt.subplots(figsize=(7.0, 6.4))
image = ax.imshow(M[np.ix_(order, order)], cmap="viridis", vmin=0, vmax=1, interpolation="nearest")
fig.colorbar(image, ax=ax, shrink=0.75, pad=0.02, label="Jaccard similarity of two models")
ax.set_xticks(range(len(order)), [models[i] for i in order], rotation=90, fontsize=5.5)
ax.set_yticks(range(len(order)), [models[i] for i in order], fontsize=5.5)
ax.tick_params(length=0)
ax.grid(False)
ax.set_title("Shared rate records (lower left) and thermochemistry entries (upper right)")
save(fig, "uc18_model_similarity")
