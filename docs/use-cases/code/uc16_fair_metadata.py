"""Use case 16. How many experimental datasets give each item of FAIR metadata?"""
import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get_all, save, style

datasets = get_all("/api/experiment-dataset/", fields="id,reference_doi,file_doi,license,file_authors,"
                   "reference_authors,apparatus,chemked_file_path,source_commit,is_valid")   # 3 requests
licences = {l["id"]: l["spdx_id"] for l in get_all("/api/license/")}
ITEMS = [  # (FAIR principle, item, test on one dataset)
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

style()
fig, ax = plt.subplots(figsize=(7, 3.6))
principles = sorted({p for p, _, _ in counts})
colour = {p: COLOURS[i] for i, p in enumerate(principles)}
bars = ax.barh([f"{item} ({p})" for p, item, _ in counts], [100 * c / n for _, _, c in counts],
               color=[colour[p] for p, _, _ in counts])
ax.bar_label(bars, labels=[f"{100 * c / n:.1f} %" for _, _, c in counts], padding=3, fontsize=8)
ax.invert_yaxis()
ax.set_xlim(0, 110)
ax.set_xlabel(f"Datasets that give the item (% of {n})")
save(fig, "uc16_fair_metadata")
