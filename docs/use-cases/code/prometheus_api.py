"""GET requests to the Prometheus API, and the plot style of the use-case examples.

Every use case imports this file. It uses only the Python standard library for the requests;
the plots need `matplotlib`.
"""
import csv
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy

BASE = os.environ.get("PROMETHEUS_API", "https://pr.omethe.us")
FIGURES = Path(os.environ.get("PROMETHEUS_FIGURES", "."))
LOG = os.environ.get("PROMETHEUS_LOG")  # optional: a CSV file that records every request
USER_AGENT = "prometheus-use-case-examples/1.0"

# Okabe-Ito colours (readable with colour-blind vision)
COLOURS = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def _request(path, params):
    """One GET request; returns the body. A list value, such as species=[5, 9], repeats the parameter."""
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as resp:   # raises HTTPError for a status >= 400
        body, status = resp.read(), resp.status
    if LOG:
        new = not Path(LOG).exists()
        with open(LOG, "a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["utc_time", "url", "status", "bytes", "sha256"])
            w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), url, status, len(body),
                        hashlib.sha256(body).hexdigest()])
    return body


def get(path, **params):
    """One GET request to a JSON endpoint. `path` is a path such as "/api/species/" or a full URL."""
    return json.loads(_request(path, params))


def get_text(path, **params):
    """One GET request whose response is a file, such as a model download."""
    return _request(path, params).decode("utf-8")


def get_all(path, **params):
    """All records of a list endpoint. The API gives at most 1,000 records a page;
    this function follows `next` until it is null. Without an ordering, the pages can overlap
    (some records come two times and others never), so the records are ordered by ID."""
    params.setdefault("page_size", 1000)
    params.setdefault("ordering", "id")
    data = get(path, **params)
    rows = list(data["results"])
    while data["next"]:
        data = get(data["next"])
        rows += data["results"]
    return rows


def species_id(inchi, **filters):
    """The ID of the one species record whose isomer has this InChI (ground state).
    For a species with two spin states, such as O2, give multiplicity=3 or 1."""
    found = get("/api/species/", inchi=inchi, has_electronic_state="false", **filters)["results"]
    if len(found) != 1:
        raise ValueError(f"{inchi}: {len(found)} species records")
    return found[0]["id"]


def model_record(name, fields="id,model_name"):
    """The model record whose model_name is exactly `name`."""
    return next(m for m in get_all("/api/kineticmodel/", search=name, fields=fields) if m["model_name"] == name)


def model_names(model_id):
    """{species record ID: the name that this model uses for the species}. A few models give two or
    more species for one species record (Shamel-Propane: H, HEG, HCFG and Halt); then the first name counts."""
    names = {}
    for n in get(f"/api/kineticmodel/{model_id}/", fields="speciesname_set")["speciesname_set"]:
        names.setdefault(n["species"], n["name"])
    return names


def find_reaction(reactants, products):
    """The reaction record with exactly these reactants and products (species record IDs; give a
    species two times when the reaction has it two times, as in CH3 + CH3)."""
    want = Counter(products)
    want.subtract(Counter(reactants))
    want = {sid: n for sid, n in want.items() if n}
    for r in get_all("/api/reaction/", species=sorted(set(reactants) | set(products))):
        if {s["species"]: s["coeff"] for s in r["stoichiometry_set"]} == want:
            return r
    raise ValueError(f"no reaction record for {reactants} = {products}")


def links(kind, species=()):
    """{model name: the IDs of the records that the model links to}, for the models that contain all
    the species given (all models when none is given). kind: "kinetics" (rate records) or "thermo"
    (thermochemistry entries)."""
    field = {"kinetics": "kineticscomment_set", "thermo": "thermocomment_set"}[kind]
    models = get_all("/api/kineticmodel/", species=list(species), fields=f"id,model_name,{field}")
    return {m["model_name"]: {c[kind] for c in m[field]} for m in models}


def equation(reaction, names):
    """The equation of a reaction record, with the species names of one model ({species record ID: name})."""
    def side(sign):
        return " + ".join((f"{int(abs(s['coeff']))} " if abs(s["coeff"]) > 1 else "") + names.get(s["species"], str(s["species"]))
                          for s in reaction["stoichiometry_set"] if s["coeff"] * sign > 0)
    return f"{side(-1)} = {side(1)}"


def paper(dataset):
    """The paper folder of a dataset (first author and year), from chemked_file_path: "Cheng 1984"."""
    return dataset["chemked_file_path"].split("/")[-2].replace("_", " ")


def formula(name):
    """A species name with subscript digits for a plot label: CH3O -> CH$_3$O."""
    return re.sub(r"(?<=[A-Za-z)])(\d+)", r"$_{\1}$", name)


def style():
    """The plot style of the use cases: TeX Gyre Heros (a free Helvetica) when it is installed, else
    Helvetica, Arial or DejaVu Sans; Okabe-Ito colours; thin axes; a light grid behind the data."""
    from matplotlib import font_manager
    for folder in ("/usr/local/texlive", "/usr/share/texlive", "/usr/share/texmf"):   # TeX Live has the fonts
        for path in Path(folder).glob("*/texmf-dist/fonts/opentype/public/tex-gyre/texgyreheros-*.otf"):
            font_manager.fontManager.addfont(str(path))
    names = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ("TeX Gyre Heros", "Helvetica", "Arial") if f in names), "DejaVu Sans")
    matplotlib.rcParams.update({
        "font.family": font, "font.size": 9, "mathtext.fontset": "custom", "mathtext.rm": font,
        "mathtext.it": f"{font}:italic", "mathtext.bf": f"{font}:bold",
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 8,
        "axes.labelsize": 9.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8,
        "axes.linewidth": 0.8, "axes.edgecolor": "#333333", "axes.labelcolor": "#1a1a1a",
        "xtick.color": "#333333", "ytick.color": "#333333", "text.color": "#1a1a1a",
        "xtick.major.width": 0.8, "ytick.major.width": 0.8, "xtick.major.size": 3.5, "ytick.major.size": 3.5,
        "xtick.minor.size": 2, "ytick.minor.size": 2, "xtick.direction": "out", "ytick.direction": "out",
        "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.prop_cycle": matplotlib.cycler(color=COLOURS), "lines.linewidth": 1.4,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight",
        "savefig.pad_inches": 0.06, "svg.fonttype": "path", "svg.hashsalt": "prometheus-use-cases",
    })


def temperature_axis(ax, ticks):
    """A temperature axis (K) on top of a plot against 1000 K / T."""
    inverse = lambda x: 1000 / numpy.maximum(x, 1e-6)
    top = ax.secondary_xaxis("top", functions=(inverse, inverse))
    top.set_xticks(ticks)
    top.set_xlabel("Temperature (K)", fontsize=8.5)


def save(fig, name):
    """Save the figure as FIGURES/<name>.svg (vector, for the web pages) and FIGURES/<name>.png (300 dpi)."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.svg", metadata={"Date": None})   # no date: the same data give the same file
    fig.savefig(FIGURES / f"{name}.png", metadata={"Software": None})
    plt.close(fig)
