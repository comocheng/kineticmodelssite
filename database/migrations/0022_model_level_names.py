"""A model's names for one species record, each with its own thermo entry, stay on that record.

The thermo and transport links say which name they belong to, and the kinetics links which names
they write. Species.variant stays until fold_species_variants has merged the variant records into
their shared records (0023 removes it); a database default lets rows be created meanwhile.

The default is set in SQL, not with Field(db_default=...), because the server runs Django 4.2
(environment.yml), which has no db_default."""
import django.db.models.deletion
from django.db import migrations, models


def _variant_default(sql):
    def run(apps, schema_editor):
        table = schema_editor.quote_name(apps.get_model("database", "Species")._meta.db_table)
        schema_editor.execute(f"ALTER TABLE {table} ALTER COLUMN {schema_editor.quote_name('variant')} {sql}")
    return run


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0021_chebyshev_range_identity"),
    ]

    operations = [
        migrations.RunPython(_variant_default("SET DEFAULT ''"), _variant_default("DROP DEFAULT")),
        migrations.AddField(
            model_name="thermocomment",
            name="species_name",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="thermo_links", to="database.speciesname"),
        ),
        migrations.AddField(
            model_name="transportcomment",
            name="species_name",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="transport_links", to="database.speciesname"),
        ),
        migrations.CreateModel(
            name="KineticsCommentName",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reactant", models.BooleanField(help_text="A reactant; a product otherwise")),
                ("kinetics_comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                       related_name="names", to="database.kineticscomment")),
                ("species_name", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="kinetics_names", to="database.speciesname")),
            ],
        ),
    ]
