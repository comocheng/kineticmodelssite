"""
Check available dictionary files on cluster
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager


class Command(BaseCommand):
    help = 'Check dictionary files on cluster'

    def handle(self, *args, **options):
        job = ClusterJob.objects.first()
        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'}
        )
        
        ssh_manager = SSHJobManager(config)
        job_path = f"{config.root_path}{job.name}"
        
        try:
            ssh_manager.connect()
            
            # List all txt files
            self.stdout.write('='*80)
            self.stdout.write('ALL .txt FILES:')
            self.stdout.write('='*80)
            stdout, _ = ssh_manager.exec_command(f'ls -lh {job_path}/*.txt {job_path}/RMG-Py-output/*.txt 2>/dev/null')
            self.stdout.write(stdout)
            
            # Check SMILES.txt
            self.stdout.write('\n' + '='*80)
            self.stdout.write('SMILES.txt CONTENT:')
            self.stdout.write('='*80)
            stdout, _ = ssh_manager.exec_command(f'cat {job_path}/SMILES.txt')
            self.stdout.write(stdout)
            
            # Check Original_RMG_dictionary.txt
            self.stdout.write('\n' + '='*80)
            self.stdout.write('Original_RMG_dictionary.txt (first 100 lines):')
            self.stdout.write('='*80)
            stdout, _ = ssh_manager.exec_command(f'cat {job_path}/RMG-Py-output/Original_RMG_dictionary.txt | head -100')
            self.stdout.write(stdout)
            
            # Check MatchedSpeciesDictionary.txt
            self.stdout.write('\n' + '='*80)
            self.stdout.write('MatchedSpeciesDictionary.txt:')
            self.stdout.write('='*80)
            stdout, _ = ssh_manager.exec_command(f'cat {job_path}/RMG-Py-output/MatchedSpeciesDictionary.txt')
            self.stdout.write(stdout)
            
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
