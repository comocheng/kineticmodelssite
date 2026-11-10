"""
Clean up jobs with incorrect status (stuck as 'running' but not actually running)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from importer_dashboard.models import ClusterJob, ImportJobConfig, ImportJobStatus
from importer_dashboard.ssh_manager import SSHJobManager


class Command(BaseCommand):
    help = 'Clean up jobs that are stuck with incorrect status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Get configuration
        config = ImportJobConfig.objects.filter(is_default=True).first()
        if not config:
            self.stdout.write(self.style.ERROR('No default configuration found'))
            return
        
        # Find jobs that claim to be running
        running_jobs = ClusterJob.objects.filter(
            status__in=[ImportJobStatus.RUNNING, ImportJobStatus.PENDING]
        )
        
        self.stdout.write(f'Found {running_jobs.count()} jobs marked as running/pending')
        self.stdout.write('')
        
        # Connect to SSH
        try:
            ssh_manager = SSHJobManager(config=config)
            
            # Get actual SLURM queue
            command = "squeue -o '%i %j' | grep port"
            stdout, stderr = ssh_manager.exec_command(command)
            
            # Parse ports in SLURM
            ports_in_slurm = set()
            for line in stdout.splitlines():
                match = re.search(r'port(\d+)', line)
                if match:
                    ports_in_slurm.add(int(match.group(1)))
            
            self.stdout.write(f'Found {len(ports_in_slurm)} jobs actually in SLURM queue')
            self.stdout.write('')
            
            # Check each "running" job
            fixed_count = 0
            for job in running_jobs:
                if job.port in ports_in_slurm:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {job.name}: Actually in SLURM queue')
                    )
                else:
                    # Not in queue - check if it completed/failed
                    if job.slurm_job_id:
                        # Check sacct
                        command = f"sacct -j {job.slurm_job_id} --format=State --noheader -P | head -1"
                        stdout, _ = ssh_manager.exec_command(command)
                        
                        if stdout:
                            state = stdout.strip()
                            
                            if state == 'COMPLETED':
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠ {job.name}: COMPLETED (was marked as {job.status})'
                                    )
                                )
                                if not dry_run:
                                    job.status = ImportJobStatus.COMPLETED
                                    job.host = None
                                    job.slurm_job_id = None
                                    if not job.completed_at:
                                        job.completed_at = timezone.now()
                                    job.save()
                                    fixed_count += 1
                            
                            elif state in ['FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY']:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f'✗ {job.name}: {state} (was marked as {job.status})'
                                    )
                                )
                                if not dry_run:
                                    job.status = ImportJobStatus.FAILED
                                    job.host = None
                                    job.slurm_job_id = None
                                    if not job.completed_at:
                                        job.completed_at = timezone.now()
                                    job.save()
                                    fixed_count += 1
                            
                            else:
                                self.stdout.write(
                                    self.style.NOTICE(
                                        f'? {job.name}: SLURM state={state}'
                                    )
                                )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'? {job.name}: No sacct data (very old job?)'
                                )
                            )
                    else:
                        self.stdout.write(
                            self.style.NOTICE(
                                f'○ {job.name}: No SLURM ID (never started?)'
                            )
                        )
            
            self.stdout.write('')
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'Would fix {fixed_count} jobs')
                )
                self.stdout.write('Run without --dry-run to apply changes')
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Fixed {fixed_count} jobs')
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            import traceback
            traceback.print_exc()


import re
