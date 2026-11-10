"""
Conversion of ChemKED quantities to the SI units of the numeric fields.

Each numeric field that has a ``*_quantity`` link (``ExperimentDatapoint.pressure`` and
``pressure_quantity``, ``IgnitionDelayDatapoint.ignition_delay`` and ``ignition_delay_quantity``,
...) holds its value in one SI unit, as its help text states, so that API range filters,
exports and simulations compare like with like. The linked ``ValueWithUnit`` keeps the value
and the unit as the source file gave them.
"""

import re
from typing import Optional

import pint

# SI unit of each kind of numeric field.
SI_UNITS = {
    "temperature": "kelvin",
    "pressure": "pascal",
    "time": "second",
    "velocity": "meter / second",
    "rate": "1 / second",
    "length": "meter",
    "volume": "meter ** 3",
    "mass_flux": "kilogram / meter ** 2 / second",
    "volumetric_flow": "meter ** 3 / second",
    "area": "meter ** 2",
    "heat_transfer_coefficient": "watt / meter ** 2 / kelvin",
}

_registry: Optional[pint.UnitRegistry] = None


class UnitConversionError(ValueError):
    """The units of a quantity are missing or cannot be converted to the SI unit."""


def _ureg() -> pint.UnitRegistry:
    global _registry
    if _registry is None:
        _registry = pint.UnitRegistry()
    return _registry


def normalize_units(units: Optional[str]) -> str:
    """Rewrite unit spellings found in ChemKED files into ones pint parses."""
    text = (units or "").strip()
    # "660. K" was split as 660 and ". K" by the importer's old number pattern.
    text = text.lstrip(".").strip()
    # pint knows "torr" but not "Torr".
    text = re.sub(r"\bTorr\b", "torr", text)
    # "cm3" -> "cm**3", "m2" -> "m**2"; exponents written with ** are left as they are.
    text = re.sub(r"(?<=[A-Za-z])(\d+)\b", r"**\1", text)
    return text


def to_si(value: Optional[float], units: Optional[str], kind: str) -> Optional[float]:
    """Return *value*, given in *units*, in the SI unit of *kind* (a key of SI_UNITS)."""
    if value is None:
        return None
    text = normalize_units(units)
    if not text:
        raise UnitConversionError(f"{value} has no units; expected {SI_UNITS[kind]}")
    try:
        return float(_ureg().Quantity(float(value), text).to(SI_UNITS[kind]).magnitude)
    except (pint.errors.PintError, AttributeError, SyntaxError, TypeError, ValueError) as exc:
        raise UnitConversionError(
            f"cannot convert {value} {units!r} to {SI_UNITS[kind]}: {exc}"
        ) from exc


def quantity_to_si(quantity, kind: str) -> Optional[float]:
    """SI value of a ValueWithUnit, or None for no quantity or a quantity given only as text."""
    if quantity is None or quantity.value is None:
        return None
    return to_si(quantity.value, quantity.units, kind)
