import os
import sys
from pathlib import Path

# Setup Django
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kms.settings')
import django
django.setup()

# Now import the function
from import_rmg_models import import_rmg_models
from django.apps import apps

# Set the RMG models path
os.environ['RMGMODELSPATH'] = '/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models'

print("Starting manual import...")
print("Check importer.log for progress")

# Run the import
import_rmg_models(apps, None)

print("\nImport completed!")

# Check results
from database.models import KineticModel
print(f"Total models in database: {KineticModel.objects.count()}")