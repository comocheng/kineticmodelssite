"""
Management command to check the species directory in RMG-Py-output to understand
where the 372 species number comes from.
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager
from importer_dashboard.incremental_sync import IncrementalVoteSync


class Command(BaseCommand):
    help = 'Check the species directory to find where 372 species comes from'

    def handle(self, *args, **options):
        # Get the first cluster job
        job = ClusterJob.objects.first()
        if not job:
            self.stdout.write(self.style.ERROR('No cluster job found'))
            return

        self.stdout.write(f'Checking job: {job.name}')
        
        # Get or create config
        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={
                'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'
            }
        )
        
        # Create SSH manager and sync
        ssh_manager = SSHJobManager(config)
        sync = IncrementalVoteSync(ssh_manager, job)
        
        job_path = f"{config.root_path}{job.name}"
        
        try:
            ssh_manager.connect()
            
            # Check species directory
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SPECIES DIRECTORY CONTENTS:')
            self.stdout.write('='*80)
            
            cmd = f'ls -1 {job_path}/RMG-Py-output/species/ | wc -l'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'Number of files in species/: {stdout.strip()}')
            
            # List some species files
            cmd = f'ls {job_path}/RMG-Py-output/species/ | head -20'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'\nFirst 20 species files:\n{stdout}')
            
            # Check if there's a species_dictionary.txt or similar
            self.stdout.write('\n' + '='*80)
            self.stdout.write('CHECKING FOR SPECIES DICTIONARIES:')
            self.stdout.write('='*80)
            
            cmd = f'ls -lh {job_path}/RMG-Py-output/*dictionary*.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(stdout if stdout else stderr)
            
            # Check the votes JSON file which might have the species list
            self.stdout.write('\n' + '='*80)
            self.stdout.write('CHECKING VOTES JSON FILE:')
            self.stdout.write('='*80)
            
            cmd = f'ls -lh {job_path}/votes_*.json'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'JSON file:\n{stdout}')
            
            # Get a sample of the JSON content
            cmd = f'head -50 {job_path}/votes_*.json'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'\nFirst 50 lines of JSON:\n{stdout}')
            
            # Check the size and structure of JSON
            cmd = f'wc -l {job_path}/votes_*.json'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'\nJSON file line count: {stdout}')
            
            # Try to parse JSON structure (just check keys)
            cmd = f'python3 -c "import json; f=open(\'{job_path}/votes_db8cff6d0de0c718b461f76ab76fa00e.json\'); d=json.load(f); print(\'JSON keys:\', list(d.keys())); print(\'\\nNumber of items per key:\'); [(print(str(k) + \':\', len(v))) for k,v in d.items() if isinstance(v, (list, dict))]"'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'\nJSON structure:\n{stdout}')
            if stderr:
                self.stdout.write(f'Errors: {stderr}')
            
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
