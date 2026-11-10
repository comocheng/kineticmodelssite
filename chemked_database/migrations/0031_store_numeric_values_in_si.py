"""Convert the numeric value fields of existing records to SI units.

sync_chemked stored the number of each quantity as the file gave it (15.6 for "15.6 atm",
13797 for "13797 us"), although the fields are documented in SI units and the API filters,
the CSV export and the simulation input read them as SI. The other import paths converted.
This migration recomputes each numeric field from its linked ValueWithUnit, which keeps the
file's value and unit, so it gives the same result for rows that were already converted.
Rows whose unit cannot be converted are left unchanged and counted.
"""

import math

from django.db import migrations, models

# (model, numeric field, kind in chemked_database.units.SI_UNITS, units column set to the SI
# unit or None). Each numeric field has a ``<field>_quantity`` link to ValueWithUnit.
QUANTITY_FIELDS = [
    ("ExperimentDatapoint", "temperature", "temperature", None),
    ("ExperimentDatapoint", "pressure", "pressure", None),
    ("IgnitionDelayDatapoint", "ignition_delay", "time", None),
    ("IgnitionDelayDatapoint", "first_stage_ignition_delay", "time", None),
    ("IgnitionDelayDatapoint", "pressure_rise", "rate", None),
    ("LaminarBurningVelocityMeasurementDatapoint", "laminar_burning_velocity", "velocity", None),
    ("LaminarBurningVelocityMeasurementDatapoint", "pressure_rise", "rate", None),
    ("LaminarBurningVelocityMeasurementDatapoint", "stretch", "rate", None),
    ("JetStirredReactorMeasurementDatapoint", "environment_temperature", "temperature", None),
    ("OutletConcentrationMeasurementDatapoint", "residence_time", "time", None),
    ("BurnerStabilizedFlameSpeciationMeasurementDatapoint", "distance", "length", None),
    ("BurnerStabilizedFlameSpeciationMeasurementDatapoint", "flow_rate", "mass_flux", None),
    ("CommonProperties", "temperature", "temperature", None),
    ("CommonProperties", "pressure", "pressure", None),
    ("CommonProperties", "pressure_rise", "rate", None),
    ("CommonProperties", "flow_rate", "mass_flux", None),
    ("CommonProperties", "reactor_volume", "volume", ("reactor_volume_units", "m3")),
    ("CommonProperties", "residence_time", "time", ("residence_time_units", "s")),
    ("RCMData", "compressed_temperature", "temperature", None),
    ("RCMData", "compressed_pressure", "pressure", None),
    ("RCMData", "compression_time", "time", None),
    ("RCMData", "stroke", "length", None),
    ("RCMData", "clearance", "length", None),
]


def _same(a, b):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)


def convert_to_si(apps, schema_editor):
    from chemked_database.units import UnitConversionError, to_si

    changed_total, skipped = 0, []
    for model_name, field, kind, units_column in QUANTITY_FIELDS:
        Model = apps.get_model("chemked_database", model_name)
        rows = (
            Model.objects.filter(**{f"{field}_quantity__value__isnull": False})
            .select_related(f"{field}_quantity")
            .order_by("pk")
        )
        changed = []
        for row in rows.iterator(chunk_size=2000):
            quantity = getattr(row, f"{field}_quantity")
            try:
                value = to_si(quantity.value, quantity.units, kind)
            except UnitConversionError:
                skipped.append(f"{model_name}.{field} {row.pk} ({quantity.value} {quantity.units!r})")
                continue
            dirty = not _same(getattr(row, field), value)
            if units_column and getattr(row, units_column[0]) != units_column[1]:
                dirty = True
            if dirty:
                setattr(row, field, value)
                if units_column:
                    setattr(row, units_column[0], units_column[1])
                changed.append(row)
        update_fields = [field] + ([units_column[0]] if units_column else [])
        Model.objects.bulk_update(changed, update_fields, batch_size=1000)
        changed_total += len(changed)

    # ExperimentDatapoint.residence_time has no quantity link. sync_chemked stored the number
    # in the file's unit and put that unit in residence_time_units; convert and set it to s.
    Datapoint = apps.get_model("chemked_database", "ExperimentDatapoint")
    changed = []
    rows = (
        Datapoint.objects.filter(residence_time__isnull=False)
        .exclude(residence_time_units__in=["s", ""])
        .order_by("pk")
    )
    for row in rows.iterator(chunk_size=2000):
        try:
            row.residence_time = to_si(row.residence_time, row.residence_time_units, "time")
        except UnitConversionError:
            skipped.append(f"ExperimentDatapoint.residence_time {row.pk} ({row.residence_time_units!r})")
            continue
        row.residence_time_units = "s"
        changed.append(row)
    Datapoint.objects.bulk_update(changed, ["residence_time", "residence_time_units"], batch_size=1000)
    changed_total += len(changed)

    if changed_total or skipped:
        print(f"\n  Converted {changed_total} numeric values to SI; {len(skipped)} left unchanged")
        for item in skipped[:20]:
            print(f"    cannot convert {item}")


class Migration(migrations.Migration):

    dependencies = [
        ("chemked_database", "0030_apparatus_institution_ref_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="experimentdatapoint",
            name="residence_time_units",
            field=models.CharField(
                blank=True,
                default="s",
                help_text="Units of residence_time: s (values are converted on import)",
                max_length=20,
            ),
        ),
        # The file's values and units stay in ValueWithUnit, and the old numbers cannot be
        # told apart from converted ones, so the conversion is not reversed.
        migrations.RunPython(convert_to_si, migrations.RunPython.noop, elidable=False),
    ]
