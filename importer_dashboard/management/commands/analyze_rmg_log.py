"""
Management command to analyze RMG.log to find where 372 species number comes from
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager


class Command(BaseCommand):
    help = 'Analyze RMG.log to find species count information'

    def handle(self, *args, **options):
        # Get the first cluster job
        job = ClusterJob.objects.first()
        if not job:
            self.stdout.write(self.style.ERROR('No cluster job found'))
            return

        self.stdout.write(f'Analyzing RMG.log for job: {job.name}')
        
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
            
            # Check for species count in RMG.log
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SEARCHING RMG.LOG FOR SPECIES COUNT:')
            self.stdout.write('='*80)
            
            cmd = f'grep -i "species" {job_path}/RMG-Py-output/RMG.log | grep -i "total\\|count\\|number" | tail -20'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'Species count mentions:\n{stdout}')
            
            # Check for model statistics at end of log
            self.stdout.write('\n' + '='*80)
            self.stdout.write('CHECKING END OF RMG.LOG FOR STATISTICS:')
            self.stdout.write('='*80)
            
            cmd = f'tail -100 {job_path}/RMG-Py-output/RMG.log'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(stdout)
            
            # Check Original_RMG_dictionary.txt to count RMG species
            self.stdout.write('\n' + '='*80)
            self.stdout.write('COUNTING SPECIES IN Original_RMG_dictionary.txt:')
            self.stdout.write('='*80)
            
            cmd = f'grep -c "^[A-Za-z0-9_]" {job_path}/RMG-Py-output/Original_RMG_dictionary.txt || echo "0"'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'Number of species in Original_RMG_dictionary.txt: {stdout.strip()}')
            
            # Check the actual content
            cmd = f'head -50 {job_path}/RMG-Py-output/Original_RMG_dictionary.txt'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f'\nFirst 50 lines of Original_RMG_dictionary.txt:\n{stdout}')
            
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
