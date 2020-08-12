from django.db import migrations

from database.scripts.import_rmg_models import import_rmg_models

class Migration(migrations.Migration):
    dependencies = [("database", "0001_initial")]

    operations = [migrations.RunPython(import_rmg_models)]
