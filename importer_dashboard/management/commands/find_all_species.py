"""
Management command to find all species in the CHEMKIN mechanism files
"""

from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager


class Command(BaseCommand):
    help = 'List all species from CHEMKIN mechanism file on cluster'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=str,
            help='Job name (default: CombFlame2013/2343-Hansen)',
            default='CombFlame2013/2343-Hansen'
        )

    def handle(self, *args, **options):
        job_name = options['job']
        
        self.stdout.write(f"Finding species for job: {job_name}")
        
        # Get job
        try:
            job = ClusterJob.objects.get(name=job_name)
        except ClusterJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Job not found: {job_name}"))
            return
        
        # Get or create config
        config, _ = ImportJobConfig.objects.get_or_create(
            name='default',
            defaults={
                'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/'
            }
        )
        
        # Create SSH manager
        ssh_manager = SSHJobManager(config)
        job_path = f"{config.root_path}/{job.name}"
        
        self.stdout.write(f"Job path: {job_path}")
        
        # List files in job directory
        self.stdout.write("\n" + "="*80)
        self.stdout.write("FILES IN JOB DIRECTORY:")
        self.stdout.write("="*80)
        
        cmd = f"ls -lh {job_path}"
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout)
        
        # Check for mechanism file
        self.stdout.write("\n" + "="*80)
        self.stdout.write("CHECKING MECHANISM.TXT:")
        self.stdout.write("="*80)
        
        cmd = f"head -50 {job_path}/mechanism.txt"
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout)
        
        # Count SPECIES section
        self.stdout.write("\n" + "="*80)
        self.stdout.write("COUNTING SPECIES IN MECHANISM:")
        self.stdout.write("="*80)
        
        # Extract species list from CHEMKIN file
        cmd = f"""awk '/SPECIES/,/END/' {job_path}/mechanism.txt | grep -v 'SPECIES' | grep -v 'END' | grep -v '^\\s*$' | wc -l"""
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(f"Species count: {stdout.strip()}")
        
        # List species names
        self.stdout.write("\n" + "="*80)
        self.stdout.write("SPECIES NAMES (first 50):")
        self.stdout.write("="*80)
        
        cmd = f"""awk '/SPECIES/,/END/' {job_path}/mechanism.txt | grep -v 'SPECIES' | grep -v 'END' | grep -v '^\\s*$' | head -50"""
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout)
        
        # Check for other database files
        self.stdout.write("\n" + "="*80)
        self.stdout.write("CHECKING FOR OTHER DATABASES:")
        self.stdout.write("="*80)
        
        cmd = f"find {job_path} -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3'"
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout if stdout.strip() else "No other databases found")
        
        # Check RMG-Py-output directory
        self.stdout.write("\n" + "="*80)
        self.stdout.write("CHECKING RMG-Py-output/:")
        self.stdout.write("="*80)
        
        cmd = f"ls -lh {job_path}/RMG-Py-output/ | head -20"
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout)
        
        self.stdout.write(self.style.SUCCESS("\nDone!"))
