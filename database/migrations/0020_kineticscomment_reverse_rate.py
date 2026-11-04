"""Each model's kinetics link can keep the model's explicit reverse rate.

A CHEMKIN line A = B with REV / A n Ea / gives the reverse rate itself. RMG-Py's CHEMKIN reader drops
it and RMG-models keeps only the forward rate, so the exports gave the reverse rate from
thermochemistry. The field starts empty (nothing exported changes); the importer and
import_explicit_reverse_rates fill it from each model's CHEMKIN file."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0019_species_variant"),
    ]

    operations = [
        migrations.AddField(
            model_name="kineticscomment",
            name="reverse_rate",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
