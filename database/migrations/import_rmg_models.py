"""Formerly imported every RMG-models model during `migrate`; now does nothing.

A data migration sees the historical models of 0001_initial, which have no
Structure.structure_key and no Species.electronic_state, so the importer fell back to the
isomer-set hash and made a second species record for a radical whose thermo entry gives one
resonance form and whose reactions give all of them. Import with the current schema instead:

    python manage.py import_rmg_models                     # all models under RMGMODELSPATH
    python manage.py import_rmg_models --model <name>      # one model

The migration is kept (an empty step) so the history of databases that applied it, and the
migrations that depend on it, stay valid.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("database", "0001_initial")]

    operations = [migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]
