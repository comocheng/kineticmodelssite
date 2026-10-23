from django.db import migrations

from database.scripts.import_rmg_models import import_rmg_models

def reverse_import(apps, schema_editor):
    """Remove all imported data"""
    KineticModel = apps.get_model('database', 'KineticModel')
    # This will cascade delete all related objects
    KineticModel.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [("database", "0001_initial")]

    operations = [migrations.RunPython(import_rmg_models)]