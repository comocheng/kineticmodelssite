"""Use case 14. In the jet-stirred-reactor experiments of the collection, which measurement gives the
most species profiles against temperature, and what do the profiles show?"""
from collections import defaultdict

import matplotlib.pyplot as plt

from prometheus_api import get, get_all, save, style

JSR = "jet stirred reactor"
# All speciation measurements of jet-stirred reactors, and all their concentration profiles (2 requests)
measurements = {m["id"]: m for m in get_all("/api/speciation-measurement/", datapoint__dataset__apparatus__kind=JSR,
                                             expand="datapoint")}
profiles = defaultdict(list)
for p in get_all("/api/concentration-profile/", measurement__datapoint__dataset__apparatus__kind=JSR):
    profiles[p["measurement"]].append(p)


def primary(m):
    return next((v["name"] for v in m["independent_variables"] if v["primary"]), "")


best = max((m for m in measurements.values() if primary(m) == "temperature"), key=lambda m: len(profiles[m["id"]]))
# A row of a profile gives the independent variables first, then the value. A further column, when
# there is one, is the uncertainty of that row: here the evaluated standard deviation
# (evaluated_standard_deviation_type "absolute", one value per row)
col = len(best["independent_variables"])
dataset = get(f"/api/experiment-dataset/{best['datapoint']['dataset']}/",
              fields="id,reference_doi,reference_year,reference_authors,chemked_file_path")
print(f"{len(measurements)} jet-stirred-reactor measurements with {sum(map(len, profiles.values()))} profiles")
print(f"measurement {best['id']} of dataset {dataset['id']} ({dataset['chemked_file_path']}, "
      f"doi {dataset['reference_doi']}): {len(profiles[best['id']])} species profiles against temperature")
for p in profiles[best["id"]]:
    x = [row[col] for row in p["values"]]
    print(f"  {p['species']['species_name']:8s} {len(x):3d} values, largest mole fraction {max(x):.2e}")

style()
fig, ax = plt.subplots(figsize=(6.8, 4.2))
major = sorted(profiles[best["id"]], key=lambda p: -max(row[col] for row in p["values"]))[:8]
for p in major:   # the 8 species with the largest mole fractions
    T = [row[0] for row in p["values"]]
    X = [row[col] for row in p["values"]]
    if all(len(row) > col + 1 for row in p["values"]):
        sd = [row[col + 1] for row in p["values"]]          # the uncertainty of each row
    elif p["evaluated_standard_deviation_type"] == "absolute":
        sd = p["evaluated_standard_deviation"]               # one uncertainty for the profile
    else:
        sd = None
    ax.errorbar(T, X, yerr=sd, marker="o", ms=3, lw=1, capsize=2, elinewidth=0.6,
                label=p["species"]["species_name"])
ax.set_yscale("log")
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("Mole fraction")
paper = dataset["chemked_file_path"].split("/")[-2].replace("_", " ")   # the paper folder: first author and year
ax.set_title(f"Jet-stirred reactor, {paper} (dataset {dataset['id']}): the 8 largest profiles", loc="left", fontsize=10)
ax.legend(fontsize=7, ncol=2)
save(fig, "uc14_species_profiles")
