"""Use case 24. Shock-tube experiments define ignition by different signals: the pressure, excited OH
(OH*) or OH. After a correlation removes the effects of temperature, pressure and mixture, do the
ignition delays of H2/O2 mixtures depend on the signal?"""
# %% Imports
import matplotlib.pyplot as plt
import numpy as np

from prometheus_api import COLOURS, get_all, save, style

H2, O2 = "1S/H2/h1H", "1S/O2/c1-2"
DILUENTS = {"1S/Ar": "Ar", "1S/N2/c1-2": "N2", "1S/He": "He"}

# %% All ignition delays of mixtures with H2, and the apparatus of each dataset
delays = get_all("/api/ignition-delay/", inchi=H2, expand="datapoint")
ids = sorted({d["datapoint"]["dataset"] for d in delays})
kind = {d["id"]: (d["apparatus"] or {}).get("kind") for n in range(0, len(ids), 300)
        for d in get_all("/api/experiment-dataset/", id__in=",".join(map(str, ids[n:n + 300])), fields="id,apparatus")}

# %% Keep shock tubes with H2, O2 and one diluent, above the crossover temperature (p <= 5 bar, or T >= 1200 K)
rows = []
for d in delays:
    dp = d["datapoint"]
    x = {s["inchi"]: s["amount"] for s in dp["composition"]["species"]}
    diluent = [DILUENTS[i] for i in x if i in DILUENTS]
    if kind[dp["dataset"]] == "shock tube" and H2 in x and O2 in x and set(x) - {H2, O2} <= DILUENTS.keys() \
            and len(diluent) == 1 and dp["temperature"] >= 1000 and (dp["pressure"] <= 5e5 or dp["temperature"] >= 1200):
        rows.append(dict(tau=d["ignition_delay"], T=dp["temperature"], p=dp["pressure"], h2=x[H2] / sum(x.values()),
                         o2=x[O2] / sum(x.values()), diluent=diluent[0], signal=d["ignition_target"], dataset=dp["dataset"]))

# %% A shock tube cannot measure a delay longer than about 50 ms: such values have a wrong unit
long = [r for r in rows if r["tau"] > 0.05]
rows = [r for r in rows if r["tau"] <= 0.05]
print(f"left out {len(long)} delays longer than 50 ms, from datasets {sorted({r['dataset'] for r in long})}")

# %% Fit ln(tau) = c0 + c1 (1000/T) + c2 ln p + c3 ln x(H2) + c4 ln x(O2) + one term for each diluent
X = np.array([[1, 1000 / r["T"], np.log(r["p"]), np.log(r["h2"]), np.log(r["o2"]), r["diluent"] == "N2",
               r["diluent"] == "He"] for r in rows], dtype=float)
y = np.log([r["tau"] for r in rows])
c, *_ = np.linalg.lstsq(X, y, rcond=None)
residual = y - X @ c
print(f"{len(rows)} shock-tube ignition delays of H2/O2/diluent above the crossover temperature, in {len({r['dataset'] for r in rows})} datasets")
print(f"  correlation: activation energy {c[1] * 8.314462618:.0f} kJ/mol, pressure exponent {c[2]:.2f}; "
      f"scatter of ln(tau) around it {np.std(residual):.2f}")

# %% The median residual of each dataset (its datapoints share one laboratory and one signal), by signal
by_dataset = {}
for r, e in zip(rows, residual):
    by_dataset.setdefault(r["dataset"], (r["signal"], []))[1].append(e)
signals = sorted({s for s, _ in by_dataset.values()}, key=lambda s: -sum(v[0] == s for v in by_dataset.values()))
means = {s: [np.median(v) for sig, v in by_dataset.values() if sig == s] for s in signals}
for s in signals:
    print(f"  {s:9s} {len(means[s]):3d} datasets: median of the dataset values {np.exp(np.median(means[s])):.2f} times "
          f"the correlation; from {np.exp(min(means[s])):.2f} to {np.exp(max(means[s])):.2f}")

# %% Plot the dataset values for each signal
style()
fig, ax = plt.subplots(figsize=(7.0, 3.3))
for k, (s, colour) in enumerate(zip(signals, COLOURS)):
    m = np.exp(means[s])
    y_pos = k + 0.3 * ((np.arange(len(m)) * 0.618) % 1 - 0.5)
    ax.scatter(m, y_pos, s=24, color=colour, alpha=0.8, edgecolors="white", linewidths=0.4, zorder=3)
    ax.plot([np.exp(np.median(means[s]))] * 2, [k - 0.3, k + 0.3], color="#1a1a1a", lw=1.6, zorder=4)
ax.axvline(1, color="#666666", lw=0.8)
ax.set_xscale("log")
ax.set_xticks([0.3, 0.5, 0.7, 1, 1.4, 2, 3], ["0.3", "0.5", "0.7", "1", "1.4", "2", "3"])
ax.xaxis.set_minor_formatter(plt.NullFormatter())
ax.set_yticks(range(len(signals)), [f"{s} ({len(means[s])} datasets)" for s in signals])
ax.set_ylim(len(signals) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.set_xlabel("Measured / correlated ignition delay: median of each dataset (black bar: median of the datasets)")
ax.set_title("H$_2$/O$_2$ ignition delays in shock tubes, by the signal that defines ignition")
save(fig, "uc24_ignition_criterion")
