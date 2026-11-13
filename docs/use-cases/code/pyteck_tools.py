"""Simulate a ChemKED dataset with a kinetic model in PyTeCK (pip install pyteck pyked "cantera>=3.1")."""
import contextlib
import functools
import io
import tempfile
import warnings
from pathlib import Path

import numpy
import yaml

from prometheus_api import get

# The species of the usual ignition targets: (InChI, has_electronic_state). PyTeCK finds a target only
# by its name, and a model can name excited OH "OHV", "OHX" or "OH(A)", or OH "oh". With Cantera 3.2,
# PyTeCK 0.2.6 stops at the first name that the model does not have. The species records give the
# model's own name, so PyTeCK finds the target at the first try.
TARGETS = {"OH": ("InChI=1S/HO/h1H", "false"), "OH*": ("InChI=1S/HO/h1H", "true"),
           "CH": ("InChI=1S/CH/h1H", "false"), "CH*": ("InChI=1S/CH/h1H", "true")}


def _float(quantity, unit):
    """A float from a PyKED quantity in this unit. The quantity can carry an uncertainty."""
    q = quantity.to(unit)
    q = getattr(q, "value", q).magnitude          # a pint Measurement keeps the value in .value
    return float(getattr(q, "nominal_value", q))  # a number of the uncertainties package


@functools.lru_cache(maxsize=None)
def _records(inchi, **filters):
    """The IDs of the species records with this InChI (one request for each InChI and filter)."""
    return [r["id"] for r in get("/api/species/", inchi=inchi, **filters)["results"]]


def species_key(chemked, names):
    """PyTeCK's species key: {name in the ChemKED file: name in the model}. It gives each mixture
    component and the ignition target (such as OH*). The InChI gives the species record, and
    `names` ({species record ID: name}, from model_names) gives the name in the model. Raises KeyError
    when the model lacks a mixture component."""
    doc = yaml.safe_load(chemked)
    mixtures = [doc.get("common-properties", {}).get("composition")] + [p.get("composition") for p in doc["datapoints"]]
    components = {c["species-name"]: c["InChI"] for m in mixtures if m for c in m["species"]}
    key = {}
    for name, inchi in components.items():
        in_model = [i for i in _records(inchi, has_electronic_state="false") if i in names]
        if len(in_model) > 1:   # two spin states in the model, as for O2: the ground state of O2 is the triplet
            in_model = [i for i in in_model if i in _records(inchi, multiplicity=3)]
        if not in_model:
            raise KeyError(f"the model has no species {name} ({inchi})")
        key[name] = names[in_model[0]]
    common = doc.get("common-properties", {}).get("ignition-type", {})
    for target in {(p.get("ignition-type") or common).get("target") for p in doc["datapoints"]}:
        for species in [target, target.rstrip("*")]:   # a model without OH* uses OH, as PyTeCK intends
            found = [i for i in _records(TARGETS[species][0], has_electronic_state=TARGETS[species][1])
                     if i in names] if species in TARGETS else []
            if found:
                key[target] = names[found[0]]
                break
    return key


def run_pyteck(chemked, cantera, key):
    """Simulate every datapoint of a ChemKED file (text) with a Cantera model (text), one after the
    other. Returns the datapoints as (T in K, p in bar, measured and simulated ignition delay in s),
    PyTeCK's error function E and the scatter sigma of the measured ln(delay)."""
    from cantera import Solution
    from pyked import ChemKED
    from pyteck.eval_model import (calculate_error_function, create_simulations, estimate_std_dev,
                                   get_changing_variable, simulation_worker)
    with tempfile.TemporaryDirectory() as folder:
        data, model = Path(folder, "dataset.yaml"), Path(folder, "model.yaml")
        data.write_text(chemked)
        model.write_text(cantera)
        species = Solution(str(model)).species_names
        props = ChemKED(data)
        measured = [_float(p.ignition_delay, "second") for p in props.datapoints]
        for p in props.datapoints:   # the model's own name of the target species (see TARGETS)
            target = p.ignition_type["target"]
            same = [s for s in species if s.upper() == target.upper()]
            p.ignition_type["target"] = key.get(target) or (same[0] if same else target)
        rows = []
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():   # PyTeCK prints and warns a lot
            warnings.simplefilter("ignore")
            sigma = estimate_std_dev(get_changing_variable(props.datapoints), numpy.log(measured))
            for sim, exp in zip(create_simulations(str(data), props), measured):
                sim = simulation_worker((sim, model, key, folder, False))
                sim.process_results()
                p = sim.properties
                rows.append((_float(p.temperature, "kelvin"), _float(p.pressure, "bar"), exp,
                             _float(sim.meta["simulated-ignition-delay"], "second")))
    E, _ = calculate_error_function([r[2] for r in rows], [r[3] for r in rows], sigma)
    return rows, float(E), float(sigma)
