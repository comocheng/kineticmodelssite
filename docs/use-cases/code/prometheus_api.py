"""GET requests to the Prometheus API, and the plot style of the use-case examples.

Every use case imports this file. It needs the `requests` and `matplotlib` packages.
"""
import csv
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import requests

BASE = os.environ.get("PROMETHEUS_API", "https://pr.omethe.us")
FIGURES = Path(os.environ.get("PROMETHEUS_FIGURES", "."))
LOG = os.environ.get("PROMETHEUS_LOG")  # optional: a CSV file that records every request

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "prometheus-use-case-examples/1.0"

# Okabe-Ito colours (readable with colour-blind vision)
COLOURS = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def _log(resp):
    if not LOG:
        return
    new = not Path(LOG).exists()
    with open(LOG, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["utc_time", "url", "status", "bytes", "sha256"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), resp.url, resp.status_code,
                    len(resp.content), hashlib.sha256(resp.content).hexdigest()])


def get(path, **params):
    """One GET request. `path` is a path such as "/api/species/" or a full URL.
    A list value, such as species=[5, 9], repeats the parameter."""
    resp = SESSION.get(path if path.startswith("http") else BASE + path, params=params, timeout=300)
    _log(resp)
    resp.raise_for_status()
    return resp.json()


def get_text(path, **params):
    """One GET request whose response is a file, such as a model download."""
    resp = SESSION.get(path if path.startswith("http") else BASE + path, params=params, timeout=300)
    _log(resp)
    resp.raise_for_status()
    return resp.text


def get_all(path, **params):
    """All records of a list endpoint. The API gives at most 1,000 records a page;
    this function follows `next` until it is null."""
    params.setdefault("page_size", 1000)
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
        "savefig.pad_inches": 0.06, "svg.fonttype": "path",
    })


def save(fig, name):
    """Save the figure as FIGURES/<name>.svg (vector, for the web pages) and FIGURES/<name>.png (300 dpi)."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.svg")
    fig.savefig(FIGURES / f"{name}.png")
    plt.close(fig)
