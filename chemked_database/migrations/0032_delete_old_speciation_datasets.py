"""Delete datasets of the four speciation types that 0033 removes.

They stored one row per condition and, in the databases seen, no measured species except one
flame dataset. Re-import them as speciation measurements from ChemKED-database with
sync_chemked, or their ReSpecTh XML through the upload page. A separate migration, as
PostgreSQL cannot alter a table that has pending row deletions in the same transaction.
"""

from django.db import migrations

# Experiment types that 0033 removes, and one no ExperimentType ever had
OLD_SPECIATION_TYPES = [
    "jet stirred reactor measurement",
    "outlet concentration measurement",
    "concentration time profile measurement",
    "burner stabilized flame speciation measurement",
    "concentration profile",
]


def delete_old_speciation_datasets(apps, schema_editor):
    ExperimentDataset = apps.get_model("chemked_database", "ExperimentDataset")
    ConcentrationProfile = apps.get_model("chemked_database", "ConcentrationProfile")
    datasets = ExperimentDataset.objects.filter(experiment_type__in=OLD_SPECIATION_TYPES)
    count = datasets.count()
    datasets.delete()
    # Profiles could only belong to concentration time profile records of those datasets
    profiles, _ = ConcentrationProfile.objects.all().delete()
    print(
        f"\n  Deleted {count} datasets of the old speciation types"
        f" and {profiles} profiles outside them"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('chemked_database', '0031_store_numeric_values_in_si'),
    ]

    operations = [
        migrations.RunPython(delete_old_speciation_datasets, migrations.RunPython.noop),
    ]
