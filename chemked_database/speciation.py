"""
Speciation measurement helpers shared by the YAML export, the REST API and the pages.
"""

import re
from collections import OrderedDict

from .models import SpeciationMeasurementDatapoint

NUMBER_RE = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*)$")


def stored_rows(rows):
    """Profile rows as the file gave them.

    PostgreSQL's jsonb writes a float such as ReSpecTh's -9.9999e+94 back as a whole number,
    which reads as an int; one beyond the exact integers of a float can only have been a float.
    """
    return [
        [float(v) if isinstance(v, int) and abs(v) > 2 ** 53 else v for v in row]
        for row in rows or []
    ]


def _number_or_text(number, text):
    """The file's text for *number* when it gave one ("0.05"), else the number."""
    match = NUMBER_RE.match(text or "")
    if match and float(match.group(1)) == number:
        return text.strip()
    return number


def profile_uncertainty_block(profile):
    """The ChemKED uncertainty block of a concentration profile, as the file gave it."""
    block = {}
    if profile.uncertainty_type:
        block["uncertainty-type"] = profile.uncertainty_type
        for key, number in (
            ("uncertainty", profile.uncertainty),
            ("upper-uncertainty", profile.upper_uncertainty),
            ("lower-uncertainty", profile.lower_uncertainty),
        ):
            if number is not None:
                block[key] = _number_or_text(number, profile.uncertainty_text)
    if profile.uncertainty_sourcetype:
        block["uncertainty-sourcetype"] = profile.uncertainty_sourcetype
    if profile.evaluated_standard_deviation is not None:
        block["evaluated-standard-deviation"] = _number_or_text(
            profile.evaluated_standard_deviation, profile.uncertainty_text
        )
    for key, value in (
        ("evaluated-standard-deviation-type", profile.evaluated_standard_deviation_type),
        ("evaluated-standard-deviation-sourcetype", profile.evaluated_standard_deviation_sourcetype),
        ("evaluated-standard-deviation-method", profile.evaluated_standard_deviation_method),
    ):
        if value:
            block[key] = value
    return block


def speciation_conditions(measurement):
    """The reactor conditions a speciation datapoint gives: label, ChemKED key and quantity."""
    conditions = []
    for key, field, _kind in SpeciationMeasurementDatapoint.CHEMKED_QUANTITIES:
        quantity = getattr(measurement, f"{field}_quantity")
        if quantity:
            label = measurement._meta.get_field(field).verbose_name
            conditions.append({"label": label[:1].upper() + label[1:], "key": key, "quantity": quantity})
    return conditions


def profile_chart_data(variables, profiles, auxiliary):
    """Plotly series of a speciation datapoint's profiles against its primary variable.

    Profiles are grouped by their units, one chart per group, so that mole fractions and
    concentrations are not drawn on one axis.
    """
    if not variables:
        return None
    axis = next((v for v in variables if v.primary), variables[0])
    column = axis.column
    amount_column = len(variables)
    groups = OrderedDict()
    for profile in profiles:
        rows = profile.values or []
        series = {
            "name": profile.species.species_name if profile.species else "unknown",
            "x": [row[column] for row in rows],
            "y": [row[amount_column] for row in rows],
        }
        if rows and all(len(row) > amount_column + 1 for row in rows):
            series["error"] = [row[amount_column + 1] for row in rows]
        groups.setdefault(profile.quantity_units, []).append(series)
    return {
        "x_label": f"{axis.name} ({axis.units})",
        "groups": [{"units": units, "series": series} for units, series in groups.items()],
        "auxiliary": [
            {
                "name": f"{profile.profile_type} ({profile.quantity_units})",
                "x_label": f"{profile.independent_name} ({profile.independent_units})",
                "x": [row[0] for row in profile.values or []],
                "y": [row[1] for row in profile.values or []],
            }
            for profile in auxiliary
        ],
    }
