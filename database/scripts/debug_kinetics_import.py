import os
import sys
from pathlib import Path

# Setup Django
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kms.settings')
import django
django.setup()

from rmgpy.data.kinetics.library import KineticsLibrary
from rmgpy import kinetics, constants
from database.models import KineticModel
import traceback

def test_kinetics_import(model_name="2-BTP"):
    """Test loading kinetics library directly"""
    
    kinetics_path = f"/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models/{model_name}/RMG-Py-kinetics-library/reactions.py"
    
    print(f"Testing kinetics import for: {model_name}")
    print(f"Kinetics path: {kinetics_path}")
    print(f"File exists: {Path(kinetics_path).exists()}")
    
    if not Path(kinetics_path).exists():
        print("Kinetics file not found!")
        return
    
    # Check file size
    file_size = Path(kinetics_path).stat().st_size
    print(f"File size: {file_size} bytes")
    
    # Read first few lines
    print("\nFirst 10 lines of reactions.py:")
    with open(kinetics_path, 'r') as f:
        for i, line in enumerate(f):
            if i < 10:
                print(f"{i+1}: {line.rstrip()}")
            else:
                break
    
    # Try to load the library
    print("\n" + "="*50)
    print("Attempting to load kinetics library...")
    
    local_context = {
        "KineticsData": kinetics.KineticsData,
        "Arrhenius": kinetics.Arrhenius,
        "ArrheniusEP": kinetics.ArrheniusEP,
        "MultiArrhenius": kinetics.MultiArrhenius,
        "MultiPDepArrhenius": kinetics.MultiPDepArrhenius,
        "PDepArrhenius": kinetics.PDepArrhenius,
        "Chebyshev": kinetics.Chebyshev,
        "ThirdBody": kinetics.ThirdBody,
        "Lindemann": kinetics.Lindemann,
        "Troe": kinetics.Troe,
        "R": constants.R,
    }
    
    try:
        library = KineticsLibrary(label=model_name)
        library.SKIP_DUPLICATES = True
        
        print("Loading library...")
        library.load(kinetics_path, local_context=local_context)
        
        print(f"\nSuccessfully loaded {len(library.entries)} entries")
        
        # Show details of first entry
        if library.entries:
            first_key = list(library.entries.keys())[0]
            first_entry = library.entries[first_key]
            print(f"\nFirst entry details:")
            print(f"  Key: {first_key}")
            print(f"  Label: {first_entry.label}")
            print(f"  Item type: {type(first_entry.item)}")
            print(f"  Data type: {type(first_entry.data)}")
            
            if hasattr(first_entry.item, 'reactants'):
                print(f"  Reactants: {[r.label for r in first_entry.item.reactants]}")
            if hasattr(first_entry.item, 'products'):
                print(f"  Products: {[p.label for p in first_entry.item.products]}")
                
    except Exception as e:
        print(f"\nERROR loading library: {type(e).__name__}: {e}")
        traceback.print_exc()
        
        # Check if it's an RMG-Py version issue
        print("\n" + "="*50)
        print("This might be due to RMG-Py version mismatch.")
        print("The code mentions needing 'rmg-py/importer' branch.")
        
        # Try to check RMG version
        try:
            import rmgpy
            print(f"\nRMG-Py location: {rmgpy.__file__}")
            if hasattr(rmgpy, '__version__'):
                print(f"RMG-Py version: {rmgpy.__version__}")
        except:
            pass

def check_multiple_models():
    """Check several models to see if it's a general problem"""
    models_to_check = ["2-BTP", "GRI-mech-3.0", "H2", "AramcoMech_2.0"]
    
    print("\nChecking multiple models:")
    print("="*50)
    
    for model in models_to_check:
        path = f"/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models/{model}/RMG-Py-kinetics-library/reactions.py"
        exists = Path(path).exists()
        size = Path(path).stat().st_size if exists else 0
        print(f"{model:20} - Exists: {exists:5} - Size: {size:,} bytes")
        test_kinetics_import(model)

if __name__ == "__main__":
    test_kinetics_import("2-BTP")
    print("\n" + "="*70 + "\n")
    check_multiple_models()