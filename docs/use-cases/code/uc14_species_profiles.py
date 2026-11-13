"""Use case 14. In the jet-stirred-reactor experiments of the collection, which measurement gives the
most species profiles against temperature, and what do the profiles show?"""
# %% Imports
from collections import defaultdict

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get, get_all, paper, save, style

# %% All speciation measurements of jet-stirred reactors, and all their concentration profiles (2 requests)
JSR = "jet stirred reactor"
measurements = get_all("/api/speciation-measurement/", datapoint__dataset__apparatus__kind=JSR, expand="datapoint")
profiles = defaultdict(list)
for p in get_all("/api/concentration-profile/", measurement__datapoint__dataset__apparatus__kind=JSR):
    profiles[p["measurement"]].append(p)

# %% The measurement against temperature with the most profiles, and its dataset
against_T = [m for m in measurements if any(v["primary"] and v["name"] == "temperature" for v in m["independent_variables"])]
best = max(against_T, key=lambda m: len(profiles[m["id"]]))
dataset = get(f"/api/experiment-dataset/{best['datapoint']['dataset']}/", fields="id,reference_doi,chemked_file_path")

# %% A row of a profile: the independent variables, the value, and (when there is one) the uncertainty
col = len(best["independent_variables"])
print(f"{len(measurements)} jet-stirred-reactor measurements with {sum(map(len, profiles.values()))} profiles")
print(f"measurement {best['id']} of dataset {dataset['id']} ({dataset['chemked_file_path']}, "
      f"doi {dataset['reference_doi']}): {len(profiles[best['id']])} species profiles against temperature")
for p in profiles[best["id"]]:
    print(f"  {p['species']['species_name']:8s} {len(p['values']):3d} values, largest mole fraction "
          f"{max(row[col] for row in p['values']):.2e}")

# %% Plot the 8 profiles with the largest mole fractions, with their uncertainties
def uncertainty(p, rows):
    if all(len(row) > col + 1 for row in rows):
        return [row[col + 1] for row in rows]              # one uncertainty for each row
    if p["evaluated_standard_deviation_type"] == "absolute":
        return p["evaluated_standard_deviation"]            # one uncertainty for the profile
    return None

style()
fig, ax = plt.subplots(figsize=(7.0, 4.0))
major = sorted(profiles[best["id"]], key=lambda p: -max(row[col] for row in p["values"]))[:8]
for p, colour in zip(major, COLOURS):
    rows = [row for row in p["values"] if row[col] > 0]    # a logarithmic axis cannot show zero
    ax.errorbar([row[0] for row in rows], [row[col] for row in rows], yerr=uncertainty(p, rows), marker="o", ms=3.5,
                lw=1.2, capsize=2, elinewidth=0.6, color=colour, mec="white", mew=0.3, label=p["species"]["species_name"])
ax.set_yscale("log")
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("Mole fraction")
ax.set_title(f"Jet-stirred reactor, {paper(dataset)} (dataset {dataset['id']}): the 8 largest profiles", pad=34)
ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.3)
save(fig, "uc14_species_profiles")
