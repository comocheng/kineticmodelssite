"""
Management command to import RMG models from the RMG-models directory.

Usage:
    python manage.py import_rmg_models                    # Import all models
    python manage.py import_rmg_models --model Harris-Butane  # Import single model
    python manage.py import_rmg_models --list             # List available models
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from database.models import (
    KineticModel, Source, Author, Authorship,
    Thermo, ThermoComment, Species, Formula, Isomer, Structure, SpeciesName,
    Efficiency, Kinetics, KineticsComment, Reaction, Stoichiometry
)


logger = logging.getLogger(__name__)


def get_models(path, skip_list=None):
    """
    Generator yielding (model_name, thermo_path, kinetics_path, source_path) for each valid model.
    
    Handles both:
    - Direct models: folder/RMG-Py-thermo-library/ThermoLibrary.py
    - Nested models: folder/subfolder/RMG-Py-thermo-library/ThermoLibrary.py
    
    For nested models, the model_name is "parent/subfolder" (e.g., "CombFlame2013/17-Malewicki")
    """
    skip_list = skip_list or []
    path = Path(path)
    
    if not path.exists():
        logger.error(f"RMG models path does not exist: {path}")
        return
    
    def check_model_dir(model_dir, model_name):
        """Check if a directory contains RMG libraries and yield model info if valid."""
        thermo_path = model_dir / "RMG-Py-thermo-library" / "ThermoLibrary.py"
        kinetics_path = model_dir / "RMG-Py-kinetics-library" / "reactions.py"
        source_path = model_dir / "source.txt"
        
        # Check if this directory has the libraries
        if thermo_path.exists() or kinetics_path.exists():
            return (
                model_name,
                str(thermo_path) if thermo_path.exists() else None,
                str(kinetics_path) if kinetics_path.exists() else None,
                str(source_path) if source_path.exists() else None,
            )
        return None
    
    for model_dir in sorted(path.iterdir()):
        if not model_dir.is_dir():
            continue
        if model_dir.name.startswith('.'):
            continue
            
        top_level_name = model_dir.name
        
        # Check skip list
        if any(skip in top_level_name for skip in skip_list):
            logger.info(f"Skipping {top_level_name} (in skip list)")
            continue
        
        # First, check if this directory itself is a model (has libraries directly)
        result = check_model_dir(model_dir, top_level_name)
        if result:
            yield result
        else:
            # No direct libraries - check subdirectories for nested models
            has_nested_models = False
            for sub_dir in sorted(model_dir.iterdir()):
                if not sub_dir.is_dir():
                    continue
                if sub_dir.name.startswith('.'):
                    continue
                
                # Check skip list for nested model
                nested_name = f"{top_level_name}/{sub_dir.name}"
                if any(skip in nested_name for skip in skip_list):
                    logger.info(f"Skipping {nested_name} (in skip list)")
                    continue
                
                result = check_model_dir(sub_dir, nested_name)
                if result:
                    has_nested_models = True
                    yield result
            
            if not has_nested_models:
                logger.debug(f"Skipping {top_level_name} (no thermo or kinetics library found)")


class Command(BaseCommand):
    help = 'Import kinetic models from RMG-models directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Import only this specific model (by folder name)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List available models without importing',
        )
        parser.add_argument(
            '--path',
            type=str,
            default=os.getenv('RMGMODELSPATH', '/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models'),
            help='Path to RMG-models directory',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without making changes',
        )

    def handle(self, *args, **options):
        path = options['path']
        specific_model = options.get('model')
        list_only = options.get('list')
        dry_run = options.get('dry_run')
        
        # Setup logging
        handler = logging.StreamHandler(self.stdout)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        self.stdout.write(f"\nRMG Models Path: {path}")
        self.stdout.write(f"Current models in database: {KineticModel.objects.count()}\n")
        
        skip_list = ["PCI2011/193-Mehl"]
        model_paths = list(get_models(path, skip_list))
        
        if list_only:
            self.list_models(model_paths)
            return
        
        if specific_model:
            # Filter to just the requested model
            model_paths = [(name, t, k, s) for name, t, k, s in model_paths if name == specific_model]
            if not model_paths:
                self.stderr.write(self.style.ERROR(f"Model '{specific_model}' not found in {path}"))
                self.stderr.write("Use --list to see available models")
                return
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN - No changes will be made ===\n"))
        
        # Import models
        imported = 0
        skipped = 0
        errors = 0
        
        for rmg_model_name, thermo_path, kinetics_path, source_path in model_paths:
            # Check if already exists
            existing = KineticModel.objects.filter(model_name=rmg_model_name).first()
            
            if existing and not specific_model:
                self.stdout.write(f"  ⏭️  {rmg_model_name} - already exists (id={existing.id})")
                skipped += 1
                continue
            
            if dry_run:
                status = "UPDATE" if existing else "NEW"
                self.stdout.write(f"  📦 [{status}] {rmg_model_name}")
                self.stdout.write(f"       Thermo: {thermo_path}")
                self.stdout.write(f"       Kinetics: {kinetics_path}")
                self.stdout.write(f"       Source: {source_path}")
                imported += 1
                continue
            
            self.stdout.write(f"\n📦 Importing: {rmg_model_name}")
            
            try:
                self.import_single_model(rmg_model_name, thermo_path, kinetics_path, source_path, update=bool(existing))
                imported += 1
                self.stdout.write(self.style.SUCCESS(f"   ✅ Successfully imported {rmg_model_name}"))
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"   ❌ Error importing {rmg_model_name}: {e}"))
                logger.exception(f"Failed to import {rmg_model_name}")
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(f"Import Summary:")
        self.stdout.write(f"  Imported: {imported}")
        self.stdout.write(f"  Skipped (existing): {skipped}")
        self.stdout.write(f"  Errors: {errors}")
        self.stdout.write(f"  Total models in database: {KineticModel.objects.count()}")

    def list_models(self, model_paths):
        """List all available models and their status"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Available Models in RMG-models directory:")
        self.stdout.write("=" * 60 + "\n")
        
        for name, thermo, kinetics, source in model_paths:
            # Check if in database
            existing = KineticModel.objects.filter(model_name=name).first()
            status = self.style.SUCCESS("✅ IN DB") if existing else self.style.WARNING("⬜ NOT IN DB")
            
            parts = []
            if thermo:
                parts.append("thermo")
            if kinetics:
                parts.append("kinetics")
            if source:
                parts.append("source")
            
            self.stdout.write(f"  {status} {name}")
            self.stdout.write(f"          Files: {', '.join(parts)}")
        
        self.stdout.write(f"\nTotal: {len(model_paths)} models available")
        
        # Show DB models not in folder
        db_names = set(KineticModel.objects.values_list('model_name', flat=True))
        folder_names = set(name for name, _, _, _ in model_paths)
        db_only = db_names - folder_names
        
        if db_only:
            self.stdout.write(f"\nModels in DB but not in folder: {', '.join(sorted(db_only))}")

    def import_single_model(self, rmg_model_name, thermo_path, kinetics_path, source_path, update=False):
        """Import a single model with all its data"""
        from database.scripts.import_rmg_models import (
            import_source, import_thermo, import_kinetics
        )
        
        # Create a models namespace with actual model classes
        models = SimpleNamespace(
            KineticModel=KineticModel,
            Source=Source,
            Author=Author,
            Authorship=Authorship,
            Thermo=Thermo,
            ThermoComment=ThermoComment,
            Species=Species,
            Formula=Formula,
            Isomer=Isomer,
            Structure=Structure,
            SpeciesName=SpeciesName,
            Efficiency=Efficiency,
            Kinetics=Kinetics,
            KineticsComment=KineticsComment,
            Reaction=Reaction,
            Stoichiometry=Stoichiometry,
        )
        
        now = datetime.now()
        
        # First, create or get the kinetic model (in its own transaction)
        with transaction.atomic():
            kinetic_model, created = KineticModel.objects.get_or_create(
                model_name=rmg_model_name,
                defaults={"info": f"Imported via management command at {now.isoformat()}"},
            )
            
            if not created:
                kinetic_model.info = f"Re-imported via management command at {now.isoformat()}"
                kinetic_model.save(update_fields=["info"])
                self.stdout.write(f"   ↻ Updated existing model (id={kinetic_model.id})")
            else:
                self.stdout.write(f"   + Created new model (id={kinetic_model.id})")
        
        # Import source (in its own transaction to isolate failures)
        if source_path:
            try:
                with transaction.atomic():
                    import_source(source_path, kinetic_model, models)
                self.stdout.write(f"   + Imported source")
            except Exception as e:
                self.stderr.write(f"   ⚠️ Source import failed: {e}")
        
        # Import thermo (in its own transaction to isolate failures)
        if thermo_path:
            try:
                with transaction.atomic():
                    import_thermo(thermo_path, kinetic_model, models)
                thermo_count = ThermoComment.objects.filter(kinetic_model=kinetic_model).count()
                self.stdout.write(f"   + Imported thermo ({thermo_count} entries)")
            except Exception as e:
                self.stderr.write(f"   ⚠️ Thermo import failed: {e}")
        
        # Import kinetics (in its own transaction to isolate failures)
        if kinetics_path:
            try:
                with transaction.atomic():
                    import_kinetics(kinetics_path, kinetic_model, models)
                kinetics_count = KineticsComment.objects.filter(kinetic_model=kinetic_model).count()
                self.stdout.write(f"   + Imported kinetics ({kinetics_count} entries)")
            except Exception as e:
                    self.stderr.write(f"   ⚠️ Kinetics import failed: {e}")
