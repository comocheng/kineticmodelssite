"""
Management command to fix job statuses

This command marks jobs that are stuck in 'pending' status but have never
been submitted to SLURM (no slurm_job_id) as 'idle'.
"""

from django.core.management.base import BaseCommand
from importer_dashboard.models import ClusterJob, ImportJobStatus


class Command(BaseCommand):
    help = 'Fix job statuses - mark never-started pending jobs as idle'

    def handle(self, *args, **options):
        # Find jobs that are pending but have no SLURM job ID
        stuck_jobs = ClusterJob.objects.filter(
            status=ImportJobStatus.PENDING,
            slurm_job_id__isnull=True
        )
        
        count = stuck_jobs.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No jobs to fix - all pending jobs have SLURM IDs')
            )
            return
        
        self.stdout.write(
            f'Found {count} pending jobs with no SLURM job ID'
        )
        
        # Update them to idle status
        updated = stuck_jobs.update(status=ImportJobStatus.IDLE, host=None)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully marked {updated} jobs as idle')
        )
        
        # Show some examples
        if updated > 0:
            self.stdout.write('\nExamples of fixed jobs:')
            for job in ClusterJob.objects.filter(status=ImportJobStatus.IDLE)[:5]:
                self.stdout.write(f'  - {job.name} (port {job.port})')
