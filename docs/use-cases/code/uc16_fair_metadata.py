"""Use case 16. How many experimental datasets give each item of FAIR metadata?"""
# %% Imports
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from prometheus_api import COLOURS, get_all, save, style

# %% The metadata fields of every dataset (3 requests), and the licence records
datasets = get_all("/api/experiment-dataset/", fields="id,reference_doi,file_doi,license,file_authors,"
                   "reference_authors,apparatus,chemked_file_path,source_commit,is_valid")
licences = {l["id"]: l["spdx_id"] for l in get_all("/api/license/")}

# %% One test for each item of metadata: (FAIR principle, item, test on one dataset)
ITEMS = [
    ("F1", "Persistent identifier of the dataset itself", lambda d: bool(d["file_doi"])),
    ("R1.1", "Licence", lambda d: d["license"] is not None),
    ("R1.2", "DOI of the paper that published the data", lambda d: bool(d["reference_doi"])),
    ("R1.2", "ORCID iD of a person who wrote the file", lambda d: any(a["orcid"] for a in d["file_authors"])),
    ("R1.2", "ORCID iD of an author of the paper", lambda d: any(a["orcid"] for a in d["reference_authors"])),
    ("R1.2", "Institution of the apparatus", lambda d: bool((d["apparatus"] or {}).get("institution"))),
    ("R1.2", "Source file and the commit of that file", lambda d: bool(d["chemked_file_path"] and d["source_commit"])),
    ("R1.3", "Valid against the ChemKED schema", lambda d: bool(d["is_valid"])),
]
n = len(datasets)
counts = [(p, item, sum(test(d) for d in datasets)) for p, item, test in ITEMS]
print(f"{n} experimental datasets")
for p, item, c in counts:
    print(f"  {p:5s} {item:45s} {c:5d}  {100 * c / n:5.1f} %")
used = {licences.get(d["license"], d["license"]) for d in datasets if d["license"] is not None}
print(f"  licences given: {', '.join(sorted(map(str, used))) or 'none'}")

# %% Plot the share of datasets that give each item, one colour for each FAIR principle
style()
principles = sorted({p for p, _, _ in counts})
colour = dict(zip(principles, COLOURS))
fig, ax = plt.subplots(figsize=(7.0, 3.3))
bars = ax.barh(range(len(counts)), [100 * c / n for _, _, c in counts], color=[colour[p] for p, _, _ in counts], height=0.65)
ax.bar_label(bars, labels=[f"{100 * c / n:.1f} %" for _, _, c in counts], padding=3, fontsize=8)
ax.set_yticks(range(len(counts)), [item for _, item, _ in counts])
ax.set_ylim(len(counts) - 0.5, -0.5)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.set_xlim(0, 112)
ax.set_xlabel(f"Datasets that give the item (% of {n})")
ax.legend(handles=[Patch(color=colour[p], label=f"FAIR {p}") for p in principles], ncol=len(principles),
          loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
save(fig, "uc16_fair_metadata")
