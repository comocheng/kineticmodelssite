import os
import sys
from pathlib import Path

# Setup Django
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kms.settings')
import django
django.setup()

from django.apps import apps
from database.models import KineticModel, Species, Reaction, Kinetics
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)

print("Current database state:")
print(f"  Kinetic Models: {KineticModel.objects.count()}")
print(f"  Species: {Species.objects.count()}")
print(f"  Reactions: {Reaction.objects.count()}")
print(f"  Kinetics: {Kinetics.objects.count()}")

# Since we already have models but no reactions, let's just import kinetics for existing models
from database.scripts.import_rmg_models import import_kinetics, safe_import
from types import SimpleNamespace

# Create models namespace
model_names = [
    "KineticModel", "Source", "Author", "Authorship", 
    "Thermo", "ThermoComment", "Species", "Formula",
    "Isomer", "Structure", "SpeciesName", "Efficiency",
    "Kinetics", "KineticsComment", "Reaction", "Stoichiometry"
]
models = SimpleNamespace()
for name in model_names:
    setattr(models, name, apps.get_model("database", name))

# Get RMG models path
rmg_models_path = "/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models"

print("\nImporting kinetics for existing models...")
success_count = 0
failed_count = 0

# First verify RMG-Py version
import rmgpy
print(f"\nUsing RMG-Py from: {rmgpy.__file__}")

for kinetic_model in KineticModel.objects.all():
    model_name = kinetic_model.model_name
    kinetics_path = f"{rmg_models_path}/{model_name}/RMG-Py-kinetics-library/reactions.py"
    
    if Path(kinetics_path).exists():
        print(f"\nProcessing {model_name}...")
        try:
            # Import kinetics directly without safe_import wrapper to see errors
            import_kinetics(kinetics_path, kinetic_model, models)
            
            # Check how many reactions were imported for this model
            model_kinetics = Kinetics.objects.filter(
                kineticscomment__kinetic_model=kinetic_model
            ).count()
            print(f"  ✓ Imported {model_kinetics} kinetics entries")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed_count += 1
            import traceback
            traceback.print_exc()
    else:
        print(f"\nSkipping {model_name} - no kinetics file found")

print("\n" + "="*60)
print(f"Import summary:")
print(f"  Models processed successfully: {success_count}")
print(f"  Models failed: {failed_count}")
print(f"\nFinal database state:")
print(f"  Kinetic Models: {KineticModel.objects.count()}")
print(f"  Species: {Species.objects.count()}")
print(f"  Reactions: {Reaction.objects.count()}")
print(f"  Kinetics: {Kinetics.objects.count()}")

# Show which models have reactions
print("\nModels with reactions:")
for model in KineticModel.objects.all():
    kinetics_count = Kinetics.objects.filter(kineticscomment__kinetic_model=model).count()
    if kinetics_count > 0:
        print(f"  {model.model_name}: {kinetics_count} kinetics entries")