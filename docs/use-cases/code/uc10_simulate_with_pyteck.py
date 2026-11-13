"""Use case 10. Download one experimental dataset and one kinetic model, and simulate the experiments
with PyTeCK: how well does the model reproduce the measured ignition delays?"""
import contextlib
import os
import statistics
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import yaml
from pyteck.eval_model import evaluate_model

from prometheus_api import COLOURS, get, get_all, get_text, save, style

DATASET = 1616                          # hydrogen/Cheng_1984: H2/O2/Ar in a shock tube
MODEL = "CombFlame2015/3755-Konnov"     # a hydrogen model


def species_key(chemked, names):
    """PyTeCK's species key: for each component of the mixture, the name that the model uses.
    The InChI of the component gives its species record, and the species record gives the name."""
    doc = yaml.safe_load(chemked)
    mixtures = [doc.get("common-properties", {}).get("composition")] + [p.get("composition") for p in doc["datapoints"]]
    # each component once: the datapoints often repeat the same mixture components
    components = {c["species-name"]: c["InChI"] for m in mixtures if m for c in m["species"]}
    key = {}
    for name, inchi in components.items():
        found = [r["id"] for r in get("/api/species/", inchi=inchi, has_electronic_state="false")["results"]]
        in_model = [i for i in found if i in names]
        if len(in_model) > 1:   # two spin states in the model, as for O2: the ground state of O2 is the triplet
            triplet = {r["id"] for r in get("/api/species/", inchi=inchi, multiplicity=3)["results"]}
            in_model = [i for i in in_model if i in triplet]
        key[name] = names[in_model[0]]
    return key


@contextlib.contextmanager
def quiet():
    """PyTeCK prints one line for each case, also from its worker processes; send them to /dev/null."""
    sys.stdout.flush()   # first write what this script printed before
    saved, null = os.dup(1), os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    try:
        yield
    finally:
        os.dup2(saved, 1)
        os.close(null)
        os.close(saved)


def main():
    model = next(m for m in get_all("/api/kineticmodel/", search=MODEL, fields="id,model_name")
                 if m["model_name"] == MODEL)
    dataset = get(f"/api/experiment-dataset/{DATASET}/", fields="id,chemked_file_path,reference_doi")
    chemked = get_text(f"/chemked/dataset/{DATASET}/export/", format="yaml")          # the ChemKED file
    cantera = get_text(f"/kineticmodel/{model['id']}/download/cantera")              # the model file
    names = {n["species"]: n["name"]
             for n in get(f"/api/kineticmodel/{model['id']}/", fields="speciesname_set")["speciesname_set"]}
    key = species_key(chemked, names)
    print(f"dataset {dataset['id']} ({dataset['chemked_file_path']}, doi {dataset['reference_doi']})")
    print(f"model {model['id']} {model['model_name']}; species key from the species records: {key}")

    # PyTeCK reads the files from folders and writes its results into the working folder
    with tempfile.TemporaryDirectory() as folder:
        here = os.getcwd()
        os.chdir(folder)
        try:
            Path("model.yaml").write_text(cantera)
            Path("dataset.yaml").write_text(chemked)
            Path("species_key.yaml").write_text(yaml.safe_dump({"model.yaml": key}))
            Path("datasets.txt").write_text("dataset.yaml\n")
            with quiet():
                result = evaluate_model("model.yaml", "species_key.yaml", "datasets.txt", data_path=".",
                                        model_path=".", results_path="results", num_threads=4)
        finally:
            os.chdir(here)

    points = result["datasets"][0]
    value = lambda text: float(text.split()[0])   # PyTeCK writes each quantity as "<value> <unit>"
    rows = sorted((value(p["temperature"]), value(p["pressure"]) / 1e5, value(p["experimental ignition delay"]),
                   value(p["simulated ignition delay"])) for p in points["datapoints"])
    ratio = [sim / exp for _, _, exp, sim in rows if sim > 0]
    print(f"{len(rows)} datapoints, {rows[0][0]:.0f} to {rows[-1][0]:.0f} K, "
          f"{min(r[1] for r in rows):.1f} to {max(r[1] for r in rows):.1f} bar")
    print(f"PyTeCK error function E = {points['error function']:.2f}; "
          f"simulated / measured ignition delay: median {statistics.median(ratio):.2f}, "
          f"from {min(ratio):.2f} to {max(ratio):.2f}")

    style()
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    T = [1000 / r[0] for r in rows]
    ax.plot(T, [r[2] * 1e6 for r in rows], "o", color="#1a1a1a", ms=5, mec="white", mew=0.4, label="measured")
    ax.plot(T, [r[3] * 1e6 for r in rows], "s", color=COLOURS[1], ms=4.5, mec="white", mew=0.4,
            label=f"simulated with PyTeCK, {model['model_name']}")
    ax.set_yscale("log")
    ticks = [t for t in (10, 20, 50, 100, 200, 500, 1000, 2000) if min(min(r[2], r[3]) for r in rows) * 5e5 <= t
             <= max(max(r[2], r[3]) for r in rows) * 2e6]
    ax.set_yticks(ticks, [str(t) for t in ticks])
    ax.yaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xlabel("1000 K / T")
    ax.set_ylabel("Ignition delay (µs)")
    top = ax.secondary_xaxis("top", functions=(lambda v: 1000 / v, lambda t: 1000 / t))
    top.set_xticks([1600, 1400, 1200, 1100, 1000])
    top.set_xlabel("Temperature (K)", fontsize=8.5)
    paper = dataset["chemked_file_path"].split("/")[-2].replace("_", " ")
    ax.set_title(f"H$_2$/O$_2$/Ar in a shock tube, {paper} (dataset {dataset['id']}): E = "
                 f"{points['error function']:.2f}", pad=30)
    ax.legend(loc="upper left")
    save(fig, "uc10_simulate_with_pyteck")


if __name__ == "__main__":   # PyTeCK starts worker processes, which import this file again
    main()
