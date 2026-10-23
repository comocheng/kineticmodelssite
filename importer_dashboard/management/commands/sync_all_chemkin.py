"""
Full sync of all CHEMKIN data (species, reactions, thermo) from cluster

This command replicates what importChemkin does on the cluster:
1. Downloads mechanism.txt, thermo.txt from cluster
2. Parses with RMG-Py's load_chemkin_file()
3. Syncs all species (372 total)
4. Syncs all reactions (8314) with kinetics
5. Syncs all thermo data (NASA polynomials)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from importer_dashboard.models import (
    ClusterJob, ImportJobConfig, Species, ChemkinReaction, ChemkinThermo
)
from importer_dashboard.ssh_manager import SSHJobManager
import tempfile
import os
import sys
import shutil

# Add RMG-Py to path
RMG_PATH = '/Users/lekiaprosper/Documents/CoMoChEng/RMG39/RMG-Py'
if RMG_PATH not in sys.path:
    sys.path.insert(0, RMG_PATH)


class Command(BaseCommand):
    help = 'Full sync of all CHEMKIN data from cluster using RMG-Py parser'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=str,
            help='Job name (default: CombFlame2013/2343-Hansen)',
            default='CombFlame2013/2343-Hansen'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before sync'
        )

    def _convert_smiles_to_adjlist(self, smiles_path, output_path):
        """Convert SMILES.txt to adjacency list format for RMG parser"""
        from rmgpy.molecule import Molecule
        
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
                    mol = Molecule().from_smiles(smiles)
                    out.write(f'{label}\n')
                    out.write(mol.to_adjacency_list())
                    out.write('\n\n')
                except Exception:
                    pass  # Skip species that can't be converted

    def handle(self, *args, **options):
        job_name = options['job']
        clear_data = options['clear']
        
        # Import RMG-Py modules
        try:
            from rmgpy.chemkin import load_chemkin_file
            from rmgpy.thermo import NASA
            self.stdout.write(self.style.SUCCESS('✓ RMG-Py modules loaded'))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Failed to import RMG-Py: {e}'))
            return
        
        # Get job
        try:
            job = ClusterJob.objects.get(name=job_name)
        except ClusterJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Job not found: {job_name}'))
            return
        
        self.stdout.write(f'\nSyncing all CHEMKIN data for job: {job.name}')
        self.stdout.write('='*80)
        
        # Clear existing data if requested
        if clear_data:
            self.stdout.write('\nClearing existing data...')
            ChemkinReaction.objects.filter(job=job).delete()
            ChemkinThermo.objects.filter(species__job=job).delete()
            Species.objects.filter(job=job, identification_status='unidentified').delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared existing data'))
        
        # Get config
        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={
                'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'
            }
        )
        
        # Create SSH manager
        ssh_manager = SSHJobManager(config)
        job_path = f"{config.root_path}{job.name}"
        temp_dir = tempfile.mkdtemp()
        
        try:
            ssh_manager.connect()
            
            # Download files
            self.stdout.write('\nDownloading files from cluster...')
            
            mechanism_path = os.path.join(temp_dir, 'mechanism.txt')
            cmd = f'cat {job_path}/mechanism.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(mechanism_path, 'w') as f:
                f.write(stdout)
            self.stdout.write(f'  ✓ mechanism.txt ({len(stdout)} bytes)')
            
            thermo_path = os.path.join(temp_dir, 'thermo.txt')
            cmd = f'cat {job_path}/thermo.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(thermo_path, 'w') as f:
                f.write(stdout)
            self.stdout.write(f'  ✓ thermo.txt ({len(stdout)} bytes)')
            
            smiles_path = os.path.join(temp_dir, 'SMILES.txt')
            cmd = f'cat {job_path}/SMILES.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            with open(smiles_path, 'w') as f:
                f.write(stdout)
            
            dict_path = os.path.join(temp_dir, 'species_dictionary.txt')
            self._convert_smiles_to_adjlist(smiles_path, dict_path)
            self.stdout.write(f'  ✓ species dictionary created')
            
            # Parse with RMG-Py
            self.stdout.write('\nParsing with RMG-Py load_chemkin_file()...')
            species_list, reaction_list = load_chemkin_file(
                mechanism_path,
                dictionary_path=dict_path,
                thermo_path=thermo_path
            )
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Parsed {len(species_list)} species'))
            self.stdout.write(self.style.SUCCESS(f'  ✓ Parsed {len(reaction_list)} reactions'))
            
            # Sync species
            self.stdout.write('\nSyncing species to database...')
            species_map = {}  # Map RMG species label to Django Species
            created_count = 0
            updated_count = 0
            
            for rmg_species in species_list:
                label = rmg_species.label
                
                # Get or create Species
                species, created = Species.objects.get_or_create(
                    job=job,
                    chemkin_label=label,
                    defaults={
                        'identification_status': 'unidentified',
                        'formula': '',
                    }
                )
                
                # Update SMILES if available
                if hasattr(rmg_species, 'molecule') and rmg_species.molecule:
                    try:
                        smiles = rmg_species.molecule[0].to_smiles()
                        if species.smiles != smiles:
                            species.smiles = smiles
                            species.save()
                            updated_count += 1
                    except Exception:
                        pass
                
                species_map[label] = species
                if created:
                    created_count += 1
            
            self.stdout.write(f'  ✓ Created {created_count} species')
            self.stdout.write(f'  ✓ Updated {updated_count} species')
            
            # Sync reactions
            self.stdout.write('\nSyncing reactions to database...')
            reaction_count = 0
            
            with transaction.atomic():
                for idx, rmg_rxn in enumerate(reaction_list, 1):
                    try:
                        # Get reactants and products
                        reactants = [s.label for s in rmg_rxn.reactants]
                        products = [s.label for s in rmg_rxn.products]
                        
                        # Get kinetics
                        kinetics = rmg_rxn.kinetics
                        if not kinetics:
                            continue
                        
                        # Extract Arrhenius parameters
                        A = kinetics.A.value_si if hasattr(kinetics, 'A') else 0.0
                        A_units = str(kinetics.A.units) if hasattr(kinetics, 'A') else ''
                        n = kinetics.n.value_si if hasattr(kinetics, 'n') else 0.0
                        Ea = kinetics.Ea.value_si if hasattr(kinetics, 'Ea') else 0.0
                        Ea_units = str(kinetics.Ea.units) if hasattr(kinetics, 'Ea') else 'J/mol'
                        
                        # Temperature range
                        temp_min = kinetics.Tmin.value_si if hasattr(kinetics, 'Tmin') and kinetics.Tmin else None
                        temp_max = kinetics.Tmax.value_si if hasattr(kinetics, 'Tmax') and kinetics.Tmax else None
                        
                        # Create or update reaction
                        ChemkinReaction.objects.update_or_create(
                            job=job,
                            index=idx,
                            defaults={
                                'equation': str(rmg_rxn),
                                'reactants': ','.join(reactants),
                                'products': ','.join(products),
                                'A': A,
                                'A_units': A_units,
                                'n': n,
                                'Ea': Ea,
                                'Ea_units': Ea_units,
                                'temp_min': temp_min,
                                'temp_max': temp_max,
                                'is_reversible': rmg_rxn.reversible,
                                'is_duplicate': rmg_rxn.duplicate,
                                'family': '',
                            }
                        )
                        reaction_count += 1
                        
                        if reaction_count % 500 == 0:
                            self.stdout.write(f'  ... {reaction_count} reactions synced')
                            
                    except Exception as e:
                        self.stdout.write(f'  Warning: Failed to sync reaction {idx}: {e}')
                        continue
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Synced {reaction_count} reactions'))
            
            # Sync thermo
            self.stdout.write('\nSyncing thermodynamics to database...')
            thermo_count = 0
            
            for rmg_species in species_list:
                if not rmg_species.thermo:
                    continue
                
                label = rmg_species.label
                if label not in species_map:
                    continue
                
                species = species_map[label]
                thermo = rmg_species.thermo
                
                # Only handle NASA polynomials
                if not isinstance(thermo, NASA):
                    continue
                
                try:
                    # Get temperature ranges
                    temp_low = thermo.Tmin.value_si
                    temp_high = thermo.Tmax.value_si
                    
                    # NASA polynomials
                    polys = thermo.polynomials
                    if len(polys) < 2:
                        continue
                    
                    low_poly = polys[0]
                    high_poly = polys[1]
                    temp_mid = low_poly.Tmax.value_si
                    
                    # Create or update thermo
                    ChemkinThermo.objects.update_or_create(
                        species=species,
                        defaults={
                            'temp_low': temp_low,
                            'temp_mid': temp_mid,
                            'temp_high': temp_high,
                            'high_a1': high_poly.c0,
                            'high_a2': high_poly.c1,
                            'high_a3': high_poly.c2,
                            'high_a4': high_poly.c3,
                            'high_a5': high_poly.c4,
                            'high_a6': high_poly.c5,
                            'high_a7': high_poly.c6,
                            'low_a1': low_poly.c0,
                            'low_a2': low_poly.c1,
                            'low_a3': low_poly.c2,
                            'low_a4': low_poly.c3,
                            'low_a5': low_poly.c4,
                            'low_a6': low_poly.c5,
                            'low_a7': low_poly.c6,
                        }
                    )
                    thermo_count += 1
                    
                except Exception as e:
                    self.stdout.write(f'  Warning: Failed to sync thermo for {label}: {e}')
                    continue
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Synced {thermo_count} thermo entries'))
            
            # Update job totals
            job.total_species = len(species_list)
            job.save()
            
            # Summary
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('SYNC COMPLETE!'))
            self.stdout.write('='*80)
            self.stdout.write(f'Total species: {len(species_list)}')
            self.stdout.write(f'Total reactions: {reaction_count}')
            self.stdout.write(f'Total thermo entries: {thermo_count}')
            self.stdout.write(f'Identified species: {Species.objects.filter(job=job, identification_status="identified").count()}')
            self.stdout.write(f'Unidentified species: {Species.objects.filter(job=job, identification_status="unidentified").count()}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError: {e}'))
            import traceback
            traceback.print_exc()
        finally:
            ssh_manager.disconnect()
            shutil.rmtree(temp_dir)

        self.stdout.write(self.style.SUCCESS('\nDone!'))
