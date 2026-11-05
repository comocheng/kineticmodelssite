"""Removes Species.variant once no record has one.

Stops while variant records are left: run `manage.py fold_species_variants --apply` first, which
merges each into its shared record and keeps its name, thermo and rate links."""
from django.db import migrations


def no_variant_records(apps, schema_editor):
    Species = apps.get_model("database", "Species")
    left = Species.objects.exclude(variant="").count()
    if left:
        raise RuntimeError(f"{left} variant species records are left: run "
                           "'python manage.py fold_species_variants --apply', then migrate again")


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0021_model_level_names"),
    ]

    operations = [
        migrations.RunPython(no_variant_records, migrations.RunPython.noop),
        migrations.RemoveField(model_name="species", name="variant"),
    ]
