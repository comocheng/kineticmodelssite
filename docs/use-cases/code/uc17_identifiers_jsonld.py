"""Use case 17. Which persistent identifiers link one experimental dataset to its paper, its authors,
its licence and the data catalogue? The answer comes from the dataset's machine-readable metadata
(schema.org JSON-LD)."""
import math

import matplotlib.pyplot as plt

from prometheus_api import COLOURS, get, get_all, save, style

# The first dataset (lowest ID) whose file author has an ORCID iD
dataset = next(d for d in get_all("/api/experiment-dataset/", fields="id,file_authors", ordering="id")
               if any(a["orcid"] for a in d["file_authors"]))
doc = get(f"/api/experiment-dataset/{dataset['id']}/metadata/")          # JSON-LD, 1 request
links = [("identifier (schema:identifier)", doc.get("schema:identifier")),
         ("paper (schema:citation)", doc.get("schema:citation")),
         ("licence (schema:license)", doc.get("schema:license")),
         ("catalogue (schema:includedInDataCatalog)", doc.get("schema:includedInDataCatalog")),
         ("source file (prom:filePath)", doc.get("prom:filePath"))]
links += [(f"contributor: {c.get('schema:name')}", c.get("schema:identifier")) for c in doc.get("prom:hasContributor", [])]
links = [(k, v) for k, v in links if v]
print(f"dataset {dataset['id']}: {doc['schema:name']} ({doc['chemked:experimentType']})")
for k, v in links:
    print(f"  {k:45s} {v}")

style()
fig, ax = plt.subplots(figsize=(8, 5))
ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.35, 1.35); ax.axis("off")
ax.text(0, 0, f"Dataset {dataset['id']}\n{doc['schema:name']}", ha="center", va="center", fontsize=10,
        bbox=dict(boxstyle="round,pad=0.5", fc=COLOURS[0], ec="none", alpha=0.9), color="white")
for i, (label, value) in enumerate(links):
    a = math.pi / 2 - 2 * math.pi * i / len(links)
    x, y = 1.25 * math.cos(a), 1.0 * math.sin(a)
    ax.annotate("", xy=(0.92 * x, 0.92 * y), xytext=(0.18 * x, 0.18 * y),
                arrowprops=dict(arrowstyle="->", color="0.45", lw=1))
    text = value if len(value) < 46 else value[:20] + "…" + value[-24:]
    ax.text(x, y, f"{label}\n{text}", ha="center", va="center", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=COLOURS[1 + i % 3], lw=1.2))
ax.set_title("Identifiers in the JSON-LD metadata of one dataset", loc="left", fontsize=10)
save(fig, "uc17_identifiers_jsonld")
