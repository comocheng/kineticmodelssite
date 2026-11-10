from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("importer_dashboard", "0009_chemkinthermo_chemkinreaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="importjobconfig",
            name="ood_base_url",
            field=models.CharField(
                default="https://ood.explorer.northeastern.edu/rnode",
                help_text=(
                    "Open OnDemand base URL for compute-node web services. "
                    "Progress will be fetched from {ood_base_url}/{host}/{port}/progress.json"
                ),
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="importjobconfig",
            name="ood_timeout_seconds",
            field=models.IntegerField(
                default=10,
                help_text="Timeout (seconds) when fetching progress.json via OOD",
            ),
        ),
    ]
