"""A model's later name for a structure it already lists gets its own species record.

Existing records keep variant "" and their hash; rebuild_model_links makes the variant records
from each model's thermo library."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0018_kineticscomment_reversible"),
    ]

    operations = [
        migrations.AddField(
            model_name="species",
            name="variant",
            field=models.CharField(blank=True, db_index=True, default="", max_length=300),
        ),
    ]
