"""Data for the interactive plots: thermo against temperature, rate coefficients against 1000/T.

Everything is computed server-side and handed to the page as JSON (json_script); the page
only draws it. Units: Cp and S in J/(mol K), H and G in kJ/mol, k in cm, mol, s units for the
reaction's order.
"""
import math
from collections import defaultdict

import numpy as np
from django.urls import reverse

from database.services.chemical_identity import ENTHALPY_DEPENDENT

THERMO_POINTS = 80
TABLE_TEMPERATURES = (300, 500, 1000, 1500, 2000, 2500)
RATE_POINTS = 60
DEFAULT_RATE_RANGE = (300.0, 3000.0)
PRESSURES_BAR = (0.01, 0.1, 1.0, 10.0, 100.0)
PDEP_TYPES = {"pdep_arrhenius", "multi_pdep_arrhenius", "chebyshev", "troe", "lindemann", "third_body"}
RATE_UNITS = {1: "s⁻¹", 2: "cm³ mol⁻¹ s⁻¹", 3: "cm⁶ mol⁻² s⁻¹"}
RECORD_PREFIX = {"rmg_library": "RMG library", "rmg_family": "RMG family"}


def _round(value, digits=5):
    return float(f"{value:.{digits}g}")


def thermo_curve(thermo, points=THERMO_POINTS):
    """Cp, H, S and G sampled inside the polynomial's own range, or None if it has none."""
    from database.services.thermo_sources import nasa_from_thermo

    tmin, tmax = thermo.temp_min_1, thermo.temp_max_2
    if not (tmin and tmax and tmax > tmin > 0):
        return None
    nasa = nasa_from_thermo(thermo)
    # The polynomial is defined on [Tmin, Tmax); stay just inside the top bound.
    temps = np.append(np.linspace(tmin, tmax, points)[:-1], math.nextafter(tmax, tmin))
    curve = {"T": [], "Cp": [], "H": [], "S": [], "G": []}
    for temperature in temps:
        try:
            values = (nasa.get_heat_capacity(temperature), nasa.get_enthalpy(temperature) / 1000,
                      nasa.get_entropy(temperature), nasa.get_free_energy(temperature) / 1000)
        except Exception:
            continue
        if not all(math.isfinite(v) for v in values):
            continue
        curve["T"].append(round(float(temperature), 2))
        for name, value in zip(("Cp", "H", "S", "G"), values):
            curve[name].append(_round(value))
    return curve if curve["T"] else None


def polynomial_key(thermo):
    """Identical polynomials (copied between models) plot as one curve."""
    return (tuple(_round(c, 7) for c in [*thermo.coeffs_poly1, *thermo.coeffs_poly2]),
            thermo.temp_min_1, thermo.temp_max_1, thermo.temp_max_2)


def _model_links(ids):
    """{model name: pk} -> links to the model pages, by name."""
    return [{"text": name, "url": reverse("kinetic-model-detail", args=[pk])} for name, pk in sorted(ids.items())]


def _record_link(record, name):
    """A link for the RMG-database source of a rate record."""
    if record.provider == "rmg_library":
        return {"text": name, "url": reverse("rmg-library-detail", args=["kinetics", record.library])}
    if record.provider == "rmg_family":
        return {"text": name, "url": reverse("rmg-family-detail", args=[record.library])}
    return {"text": name, "url": record.source_url or ""}


def _label(names, fallback):
    names = sorted(set(names))
    if not names:
        return fallback, []
    return (names[0] if len(names) == 1 else f"{names[0]} +{len(names) - 1}"), names


def record_label(record):
    if record.provider == "atct_constrained":
        return f"ATcT-constrained ({record.heat_capacity_source.get_provider_display()} Cp, S)"
    if record.provider == "group_additivity":
        return "Group additivity estimate"
    return f"{record.get_provider_display()}: {record.label}"


def species_thermo_plot(thermo_rows, records):
    """Model thermo (identical polynomials grouped) plus source records with NASA curves."""
    groups = {}
    for thermo in thermo_rows:
        group = groups.setdefault(polynomial_key(thermo), {"thermo": thermo, "models": [], "ids": {}})
        for comment in thermo.thermocomment_set.all():
            group["models"].append(comment.kinetic_model.model_name)
            group["ids"][comment.kinetic_model.model_name] = comment.kinetic_model_id
    curves = []
    for group in sorted(groups.values(), key=lambda g: (-len(set(g["models"])), g["thermo"].pk)):
        curve = thermo_curve(group["thermo"])
        if curve:
            label, models = _label(group["models"], "Imported model thermo")
            curves.append({"label": label, "kind": "model", "models": models, "links": _model_links(group["ids"]),
                           "url": reverse("thermo-detail", args=[group["thermo"].pk]), **curve})
    points = []
    # RMG thermo libraries repeat common species (methane is in ~20); identical polynomials plot once.
    library_groups = {}
    for record in records:
        if record.provider == "rmg_thermo_library" and record.nasa_thermo_id:
            group = library_groups.setdefault(polynomial_key(record.nasa_thermo), {"record": record, "libraries": []})
            group["libraries"].append(record.raw_data.get("library") or record.external_id.split(":")[0])
    for group in library_groups.values():
        curve = thermo_curve(group["record"].nasa_thermo)
        if curve:
            label, libraries = _label(group["libraries"], "RMG library")
            curves.append({"label": f"RMG library: {label}", "kind": "rmg_thermo_library", "models": [],
                           "libraries": libraries, "url": reverse("thermo-detail", args=[group["record"].nasa_thermo_id]),
                           "links": [{"text": f"RMG library: {name}", "url": reverse("rmg-library-detail", args=["thermo", name])}
                                     for name in libraries], **curve})
    for record in records:
        if record.provider == "rmg_thermo_library":
            continue
        if record.nasa_thermo_id:
            curve = thermo_curve(record.nasa_thermo)
            if curve:
                curves.append({"label": record_label(record), "kind": record.provider,
                               "models": [], "url": reverse("thermo-detail", args=[record.nasa_thermo_id]), **curve})
        if record.provider == "atct" and record.enthalpy_298 is not None:
            points.append({"label": f"ATcT {record.external_id}", "kind": "atct", "T": [298.15],
                           "H": [record.enthalpy_298 / 1000],
                           "dH": [record.uncertainty_298 / 1000] if record.uncertainty_298 is not None else None})
        if record.provider == "group_additivity" and record.raw_data.get("T_K"):
            points.append({"label": "Group additivity Cp table", "kind": "group_additivity",
                           "T": record.raw_data["T_K"], "Cp": [_round(v) for v in record.raw_data["Cp_J_mol_K"]]})
    return {"curves": curves, "points": points, "table_temperatures": TABLE_TEMPERATURES}


def single_thermo_plot(thermo, label):
    curve = thermo_curve(thermo)
    return {"curves": [{"label": label, "kind": "model", "models": [], "url": "", **curve}] if curve else [],
            "points": [], "table_temperatures": TABLE_TEMPERATURES}


def reaction_order(reaction):
    return int(round(sum(-coeff for coeff in reaction.stoichiometry_set.values_list("coeff", flat=True) if coeff < 0)))


def rate_curve(kinetics, order, points=RATE_POINTS):
    """log-ready k against 1000/T at each plotted pressure, or None if it can't be evaluated."""
    data = kinetics.data
    try:
        rmg = data.to_rmg(kinetics.min_temp, kinetics.max_temp, kinetics.min_pressure, kinetics.max_pressure, [])
    except Exception:
        return None
    if type(rmg).__name__ in ENTHALPY_DEPENDENT:
        return None
    tmin = kinetics.min_temp or DEFAULT_RATE_RANGE[0]
    tmax = kinetics.max_temp or DEFAULT_RATE_RANGE[1]
    inverse = np.linspace(1000.0 / tmax, 1000.0 / tmin, points)
    pdep = data.type in PDEP_TYPES
    pressures = list(PRESSURES_BAR) if pdep else [1.0]
    if pdep and kinetics.min_pressure and kinetics.max_pressure:
        # PLOG and Chebyshev fits are only defined inside their pressure range (5% slack, so
        # a fit from 0.1 atm still offers 0.1 bar).
        pressures = [p for p in pressures
                     if 0.95 * kinetics.min_pressure <= p * 1e5 <= 1.05 * kinetics.max_pressure] or [1.0]
    factor = 1e6 ** (order - 1)  # SI (m³) to cm³ per extra reactant
    values = {}
    for pressure in pressures:
        series = []
        for x in inverse:
            try:
                k = rmg.get_rate_coefficient(1000.0 / x, pressure * 1e5) * factor
                series.append(_round(k) if k > 0 and math.isfinite(k) else None)
            except Exception:
                series.append(None)
        values[str(pressure)] = series
    if not any(v is not None for series in values.values() for v in series):
        return None
    return {"x": [round(float(x), 5) for x in inverse], "T": [round(1000.0 / float(x), 1) for x in inverse],
            "pdep": pdep, "pressures": pressures, "k": values,
            "valid_range": [kinetics.min_temp, kinetics.max_temp] if kinetics.min_temp else None}


def reaction_rate_plot(reaction):
    order = reaction_order(reaction)
    names_of, ids_of = defaultdict(list), defaultdict(dict)
    from database.models import KineticsComment
    for kinetics_id, name, model_id in KineticsComment.objects.filter(kinetics__reaction=reaction).values_list(
            "kinetics_id", "kinetic_model__model_name", "kinetic_model_id"):
        names_of[kinetics_id].append(name)
        ids_of[kinetics_id][name] = model_id
    series = []
    for kinetics in reaction.kinetics_set.all():
        curve = rate_curve(kinetics, order)
        if curve:
            label, models = _label(names_of[kinetics.pk], f"Kinetics {kinetics.pk}")
            series.append({"label": label, "kind": "model", "models": models, "type": kinetics.type,
                           "links": _model_links(ids_of[kinetics.pk]),
                           "url": reverse("kinetics-detail", args=[kinetics.pk]), **curve})
    # Most widely used rate first, so its colour is stable on the page.
    series.sort(key=lambda s: (-len(s["models"]), s["label"]))
    # RMG-database counterparts written the same way as this row. Common reactions
    # are in dozens of RMG libraries; records with the same rate are drawn once.
    if reaction.canonical_key:
        from database.models import KineticsRecord
        from database.services.chemical_identity import rates_match
        groups = []
        for record in KineticsRecord.objects.filter(reaction__canonical_key=reaction.canonical_key).order_by("provider", "library"):
            if record.canonical_direction != reaction.canonical_direction:
                continue
            group = next((g for g in groups if g["provider"] == record.provider and record.rate_fingerprint
                          and rates_match(g["record"].rate_fingerprint, record.rate_fingerprint)), None)
            name = record.library if record.provider != "rmg_family" else f"{record.library} estimate"
            if group:
                if name not in group["sources"]:
                    group["sources"].append(name)
                    group["links"].append(_record_link(record, name))
            else:
                groups.append({"provider": record.provider, "record": record, "sources": [name],
                               "links": [_record_link(record, name)]})
        for group in groups:
            record = group["record"]
            curve = rate_curve(record, order)
            if curve:
                label, sources = _label(group["sources"], record.library)
                series.append({"label": f"{RECORD_PREFIX[record.provider]}: {label}", "kind": record.provider,
                               "models": sources, "type": record.type, "url": "",
                               "links": sorted(group["links"], key=lambda link: link["text"]), **curve})
    return {"order": order, "units": RATE_UNITS.get(order, f"order {order}"), "pressures": list(PRESSURES_BAR),
            "series": series}


def single_rate_plot(kinetics, label):
    order = reaction_order(kinetics.reaction)
    curve = rate_curve(kinetics, order)
    return {"order": order, "units": RATE_UNITS.get(order, f"order {order}"), "pressures": list(PRESSURES_BAR),
            "series": [{"label": label, "kind": "model", "models": [], "type": kinetics.type, "url": "", **curve}] if curve else []}
