"""
Show raw SPECIES and REACTIONS sections from mechanism.txt
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager


class Command(BaseCommand):
    help = 'Show raw SPECIES and REACTIONS format from mechanism.txt'

    def handle(self, *args, **options):
        job = ClusterJob.objects.first()
        if not job:
            self.stdout.write(self.style.ERROR('No cluster job found'))
            return

        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'}
        )
        
        ssh_manager = SSHJobManager(config)
        job_path = f"{config.root_path}{job.name}"
        
        try:
            ssh_manager.connect()
            
            # Show SPECIES section
            self.stdout.write('='*80)
            self.stdout.write('SPECIES SECTION (first 200 lines):')
            self.stdout.write('='*80)
            
            cmd = f'awk "/SPECIES/,/END/" {job_path}/mechanism.txt | head -200'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(stdout)
            
            # Show REACTIONS section
            self.stdout.write('\n' + '='*80)
            self.stdout.write('REACTIONS SECTION (first 100 lines):')
            self.stdout.write('='*80)
            
            cmd = f'awk "/REACTIONS/,/END/" {job_path}/mechanism.txt | head -100'
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(stdout)
            
        finally:
            ssh_manager.disconnect()

        self.stdout.write(self.style.SUCCESS('\nDone!'))
