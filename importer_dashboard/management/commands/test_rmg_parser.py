"""
Test RMG-Py's CHEMKIN parser to load mechanism exactly like importChemkin does
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager
import tempfile
import os
import sys

# Add RMG-Py to path
RMG_PATH = '/Users/lekiaprosper/Documents/CoMoChEng/RMG39/RMG-Py'
if RMG_PATH not in sys.path:
    sys.path.insert(0, RMG_PATH)


class Command(BaseCommand):
    help = 'Test RMG-Py chemkin parser on cluster mechanism files'

    def _convert_smiles_to_adjlist(self, smiles_path, output_path):
        """Convert SMILES.txt to adjacency list format"""
        from rmgpy.molecule import Molecule
        from rmgpy.species import Species as RMGSpecies
        
        with open(smiles_path, 'r') as f:
            lines = f.readlines()
        
        with open(output_path, 'w') as out:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                
                label, smiles = parts
                try:
                    # Create molecule from SMILES
                    mol = Molecule().from_smiles(smiles)
                    # Write adjacency list
                    out.write(f'{label}\n')
                    out.write(mol.to_adjacency_list())
                    out.write('\n\n')
                except Exception as e:
                    # Skip species that can't be converted
                    self.stdout.write(f'Warning: Could not convert {label}: {smiles} - {e}')

    def handle(self, *args, **options):
        # Import RMG-Py's chemkin module
        try:
            from rmgpy.chemkin import load_chemkin_file
            from rmgpy.species import Species as RMGSpecies
            self.stdout.write(self.style.SUCCESS('✓ Successfully imported rmgpy.chemkin'))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Failed to import RMG-Py: {e}'))
            return

        # Get the first cluster job
        job = ClusterJob.objects.first()
        if not job:
            self.stdout.write(self.style.ERROR('No cluster job found'))
            return

        self.stdout.write(f'Testing RMG parser for job: {job.name}')
        
        # Get or create config
        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={
                'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'
            }
        )
        
        # Create SSH manager
        ssh_manager = SSHJobManager(config)
        job_path = f"{config.root_path}{job.name}"
        
        try:
            ssh_manager.connect()
            
            # Download required files to temp directory
            temp_dir = tempfile.mkdtemp()
            self.stdout.write(f'Temp directory: {temp_dir}')
            
            self.stdout.write('\n' + '='*80)
            self.stdout.write('DOWNLOADING FILES FROM CLUSTER')
            self.stdout.write('='*80)
            
            # Download mechanism.txt
            mechanism_path = os.path.join(temp_dir, 'mechanism.txt')
            cmd = f'cat {job_path}/mechanism.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(mechanism_path, 'w') as f:
                f.write(stdout)
            self.stdout.write(f'✓ Downloaded mechanism.txt ({len(stdout)} bytes)')
            
            # Download thermo.txt
            thermo_path = os.path.join(temp_dir, 'thermo.txt')
            cmd = f'cat {job_path}/thermo.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(thermo_path, 'w') as f:
                f.write(stdout)
            self.stdout.write(f'✓ Downloaded thermo.txt ({len(stdout)} bytes)')
            
            # Download SMILES.txt - simpler species definitions
            smiles_path = os.path.join(temp_dir, 'SMILES.txt')
            cmd = f'cat {job_path}/SMILES.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(smiles_path, 'w') as f:
                f.write(stdout)
            self.stdout.write(f'✓ Downloaded SMILES.txt ({len(stdout)} bytes)')
            
            # Convert SMILES.txt to adjacency list format
            dict_path = os.path.join(temp_dir, 'species_dictionary.txt')
            self._convert_smiles_to_adjlist(smiles_path, dict_path)
            self.stdout.write(f'✓ Created species dictionary from SMILES')
            
            # Parse with RMG-Py's load_chemkin_file
            self.stdout.write('\n' + '='*80)
            self.stdout.write('PARSING WITH RMG-Py load_chemkin_file()')
            self.stdout.write('='*80)
            
            species_list, reaction_list = load_chemkin_file(
                mechanism_path,
                dictionary_path=dict_path,
                thermo_path=thermo_path
            )
            
            self.stdout.write(self.style.SUCCESS(f'✓ Parsed successfully!'))
            self.stdout.write(f'  Species found: {len(species_list)}')
            self.stdout.write(f'  Reactions found: {len(reaction_list)}')
            
            # Display sample species
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SAMPLE SPECIES (first 10):')
            self.stdout.write('='*80)
            
            for i, species in enumerate(species_list[:10], 1):
                self.stdout.write(f'\n{i}. {species.label}')
                self.stdout.write(f'   Index: {species.index}')
                if hasattr(species, 'molecule') and species.molecule:
                    mol = species.molecule[0]
                    self.stdout.write(f'   SMILES: {mol.to_smiles()}')
                if species.thermo:
                    H298 = species.thermo.get_enthalpy(298.15) / 4184.0  # Convert to kcal/mol
                    self.stdout.write(f'   H298: {H298:.2f} kcal/mol')
            
            # Display sample reactions
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SAMPLE REACTIONS (first 5):')
            self.stdout.write('='*80)
            
            for i, reaction in enumerate(reaction_list[:5], 1):
                self.stdout.write(f'\n{i}. {reaction}')
                self.stdout.write(f'   Reactants: {[s.label for s in reaction.reactants]}')
                self.stdout.write(f'   Products: {[s.label for s in reaction.products]}')
                
                if reaction.kinetics:
                    # Try to get Arrhenius parameters
                    kinetics = reaction.kinetics
                    if hasattr(kinetics, 'A'):
                        self.stdout.write(f'   A: {kinetics.A.value_si:.2e} {kinetics.A.units}')
                    if hasattr(kinetics, 'n'):
                        self.stdout.write(f'   n: {kinetics.n.value_si}')
                    if hasattr(kinetics, 'Ea'):
                        self.stdout.write(f'   Ea: {kinetics.Ea.value_si:.2f} {kinetics.Ea.units}')
                    if hasattr(kinetics, 'Tmin') and kinetics.Tmin:
                        self.stdout.write(f'   Temp range: {kinetics.Tmin.value_si}-{kinetics.Tmax.value_si} K')
                
                if reaction.duplicate:
                    self.stdout.write(f'   DUPLICATE')
            
            # Analyze thermo data
            self.stdout.write('\n' + '='*80)
            self.stdout.write('THERMODYNAMICS DATA:')
            self.stdout.write('='*80)
            
            species_with_thermo = [s for s in species_list if s.thermo]
            self.stdout.write(f'Species with thermo data: {len(species_with_thermo)}')
            
            # Sample thermo
            if species_with_thermo:
                species = species_with_thermo[0]
                self.stdout.write(f'\nSample: {species.label}')
                thermo = species.thermo
                self.stdout.write(f'  Thermo type: {type(thermo).__name__}')
                if hasattr(thermo, 'Tmin'):
                    self.stdout.write(f'  Temp range: {thermo.Tmin.value_si}-{thermo.Tmax.value_si} K')
                
                # Calculate properties at 298K
                T = 298.15
                H = thermo.get_enthalpy(T) / 4184.0  # kcal/mol
                S = thermo.get_entropy(T) / 4.184  # cal/mol/K
                Cp = thermo.get_heat_capacity(T) / 4.184  # cal/mol/K
                self.stdout.write(f'  At 298K:')
                self.stdout.write(f'    H: {H:.2f} kcal/mol')
                self.stdout.write(f'    S: {S:.2f} cal/mol/K')
                self.stdout.write(f'    Cp: {Cp:.2f} cal/mol/K')
            
            # Summary
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SUMMARY')
            self.stdout.write('='*80)
            self.stdout.write(f'Total species: {len(species_list)}')
            self.stdout.write(f'Total reactions: {len(reaction_list)}')
            self.stdout.write(f'Species with thermo: {len(species_with_thermo)}')
            self.stdout.write(f'Species with molecules: {len([s for s in species_list if hasattr(s, "molecule") and s.molecule])}')
            
            # Check for duplicate reactions
            duplicates = [r for r in reaction_list if r.duplicate]
            self.stdout.write(f'Duplicate reactions: {len(duplicates)}')
            
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            import traceback
            traceback.print_exc()
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
