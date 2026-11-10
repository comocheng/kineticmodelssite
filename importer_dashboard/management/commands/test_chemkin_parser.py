"""
Test CHEMKIN parser on the cluster mechanism files
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager
from importer_dashboard.chemkin_parser import ChemkinParser, ThermoParser
import tempfile
import os


class Command(BaseCommand):
    help = 'Test CHEMKIN parser by downloading and parsing mechanism files'

    def handle(self, *args, **options):
        # Get the first cluster job
        job = ClusterJob.objects.first()
        if not job:
            self.stdout.write(self.style.ERROR('No cluster job found'))
            return

        self.stdout.write(f'Testing parser for job: {job.name}')
        
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
            
            # Download mechanism.txt
            self.stdout.write('\n' + '='*80)
            self.stdout.write('DOWNLOADING MECHANISM.TXT')
            self.stdout.write('='*80)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_mech:
                mechanism_path = tmp_mech.name
                cmd = f'cat {job_path}/mechanism.txt'
                stdout, stderr = ssh_manager.exec_command(cmd)
                tmp_mech.write(stdout)
            
            self.stdout.write(f'Downloaded to: {mechanism_path}')
            
            # Download thermo.txt
            self.stdout.write('\n' + '='*80)
            self.stdout.write('DOWNLOADING THERMO.TXT')
            self.stdout.write('='*80)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_thermo:
                thermo_path = tmp_thermo.name
                cmd = f'cat {job_path}/thermo.txt'
                stdout, stderr = ssh_manager.exec_command(cmd)
                tmp_thermo.write(stdout)
            
            self.stdout.write(f'Downloaded to: {thermo_path}')
            
            # Parse species
            self.stdout.write('\n' + '='*80)
            self.stdout.write('PARSING SPECIES')
            self.stdout.write('='*80)
            
            parser = ChemkinParser(mechanism_path)
            species = parser.parse_species()
            
            self.stdout.write(f'Found {len(species)} species')
            self.stdout.write(f'\nFirst 10 species:')
            for sp in species[:10]:
                self.stdout.write(f'  {sp.index}: {sp.name}')
            
            # Parse reactions
            self.stdout.write('\n' + '='*80)
            self.stdout.write('PARSING REACTIONS')
            self.stdout.write('='*80)
            
            reactions = parser.parse_reactions()
            
            self.stdout.write(f'Found {len(reactions)} reactions')
            self.stdout.write(f'\nFirst 5 reactions:')
            for rxn in reactions[:5]:
                self.stdout.write(f'\n  Reaction {rxn.index}: {rxn.equation}')
                self.stdout.write(f'    Reactants: {rxn.reactants}')
                self.stdout.write(f'    Products: {rxn.products}')
                self.stdout.write(f'    A={rxn.A:.2e}, n={rxn.n}, Ea={rxn.Ea}')
                if rxn.is_duplicate:
                    self.stdout.write(f'    DUPLICATE')
            
            # Parse thermodynamics
            self.stdout.write('\n' + '='*80)
            self.stdout.write('PARSING THERMODYNAMICS')
            self.stdout.write('='*80)
            
            thermo_parser = ThermoParser(thermo_path)
            thermo_data = thermo_parser.parse_thermo()
            
            self.stdout.write(f'Found {len(thermo_data)} thermo entries')
            self.stdout.write(f'\nFirst 5 thermo entries:')
            for thermo in thermo_data[:5]:
                self.stdout.write(f'\n  {thermo.name} ({thermo.formula})')
                self.stdout.write(f'    Phase: {thermo.phase}')
                self.stdout.write(f'    Temp range: {thermo.temp_low} - {thermo.temp_high} K (mid: {thermo.temp_mid})')
                self.stdout.write(f'    High-T coeffs: {thermo.high_temp_poly.coeffs[:3]}...')
            
            # Summary
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SUMMARY')
            self.stdout.write('='*80)
            self.stdout.write(f'Species parsed: {len(species)}')
            self.stdout.write(f'Reactions parsed: {len(reactions)}')
            self.stdout.write(f'Thermo entries parsed: {len(thermo_data)}')
            
            # Cleanup temp files
            os.unlink(mechanism_path)
            os.unlink(thermo_path)
            
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
