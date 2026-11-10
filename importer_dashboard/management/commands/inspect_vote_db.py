"""
Management command to inspect the vote database schema on the cluster
"""

from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobConfig
from importer_dashboard.ssh_manager import SSHJobManager
from importer_dashboard.incremental_sync import IncrementalVoteSync


class Command(BaseCommand):
    help = 'Inspect vote database schema and contents on cluster'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=str,
            help='Job name to inspect (default: CombFlame2013/2343-Hansen)',
            default='CombFlame2013/2343-Hansen'
        )

    def handle(self, *args, **options):
        job_name = options['job']
        
        self.stdout.write(f"Inspecting vote database for job: {job_name}")
        
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
        
        # Create SSH manager and sync
        ssh_manager = SSHJobManager(config)
        sync = IncrementalVoteSync(ssh_manager, job)
        
        self.stdout.write(f"Database path: {sync.db_path}")
        
        # Get tables
        self.stdout.write("\n" + "="*80)
        self.stdout.write("TABLES IN DATABASE:")
        self.stdout.write("="*80)
        
        cmd = f"sqlite3 {sync.db_path} '.tables'"
        stdout, stderr = ssh_manager.exec_command(cmd)
        self.stdout.write(stdout)
        
        # Parse table names
        table_names = stdout.strip().split()
        
        # Get schema for each table
        self.stdout.write("\n" + "="*80)
        self.stdout.write("DATABASE SCHEMA:")
        self.stdout.write("="*80)
        
        for table in table_names:
            cmd = f"sqlite3 {sync.db_path} '.schema {table}'"
            stdout, stderr = ssh_manager.exec_command(cmd)
            self.stdout.write(f"\n{stdout}")
        
        # Count records in each table
        self.stdout.write("\n" + "="*80)
        self.stdout.write("RECORD COUNTS:")
        self.stdout.write("="*80)
        
        for table in table_names:
            cmd = f"sqlite3 {sync.db_path} 'SELECT COUNT(*) FROM {table}'"
            stdout, stderr = ssh_manager.exec_command(cmd)
            count = stdout.strip()
            self.stdout.write(f"{table}: {count}")
        
        # Sample data from key tables
        self.stdout.write("\n" + "="*80)
        self.stdout.write("SAMPLE DATA (first 3 rows):")
        self.stdout.write("="*80)
        
        for table in table_names:
            self.stdout.write(f"\n--- {table} ---")
            cmd = f"sqlite3 {sync.db_path} -json 'SELECT * FROM {table} LIMIT 3'"
            stdout, stderr = ssh_manager.exec_command(cmd)
            if stdout.strip():
                import json
                try:
                    data = json.loads(stdout)
                    for row in data:
                        self.stdout.write(f"  {row}")
                except json.JSONDecodeError:
                    self.stdout.write(f"  {stdout[:200]}")
        
        # Close SSH
        ssh_manager.close()
        
        self.stdout.write(self.style.SUCCESS("\nInspection complete!"))
