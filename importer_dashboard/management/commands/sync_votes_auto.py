"""
Auto-sync votes from all running cluster jobs

This command connects to running jobs via SSH and syncs their vote databases
to the Django dashboard. Should be run periodically (e.g., every 5 minutes).

Usage:
    python manage.py sync_votes_auto
    python manage.py sync_votes_auto --job-name "CombFlame2014/885-Xiong"
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from importer_dashboard.models import ClusterJob, ImportJobStatus
from importer_dashboard.incremental_sync import sync_job_votes_incremental
from importer_dashboard.ssh_manager import SSHJobManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-sync votes from running cluster jobs via SSH'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job-name',
            type=str,
            help='Sync specific job by name (default: all running jobs)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Minimum seconds between syncs for same job (default: 300)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )

    def handle(self, *args, **options):
        job_name = options.get('job_name')
        interval = options.get('interval', 300)
        dry_run = options.get('dry_run', False)
        
        # Get jobs to sync
        if job_name:
            jobs = ClusterJob.objects.filter(name=job_name)
            if not jobs.exists():
                self.stdout.write(self.style.ERROR(f'❌ Job not found: {job_name}'))
                return
        else:
            # Sync all running jobs
            jobs = ClusterJob.objects.filter(status=ImportJobStatus.RUNNING)
        
        if not jobs.exists():
            self.stdout.write(self.style.WARNING('⚠️  No running jobs found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'🔄 Found {jobs.count()} job(s) to sync\n'))
        
        total_synced = 0
        total_skipped = 0
        total_failed = 0
        
        for job in jobs:
            self.stdout.write(f'Job: {job.name} (port {job.port})')
            
            # Check if we should skip based on last sync time
            last_sync = job.sync_logs.filter(
                sync_type='incremental_votes',
                success=True
            ).order_by('-synced_at').first()
            
            if last_sync:
                time_since_sync = (timezone.now() - last_sync.synced_at).total_seconds()
                if time_since_sync < interval:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⏭️  Skipping - last synced {int(time_since_sync)}s ago '
                            f'(interval: {interval}s)\n'
                        )
                    )
                    total_skipped += 1
                    continue
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  🔍 [DRY RUN] Would sync this job\n'))
                continue
            
            try:
                # Run incremental sync
                result = sync_job_votes_incremental(job)
                
                if result.get('status') == 'success':
                    species_count = result.get('species_synced', 0)
                    candidates_count = result.get('candidates_synced', 0)
                    votes_count = result.get('votes_synced', 0)
                    thermo_count = result.get('thermo_matches_synced', 0)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ Synced: {species_count} species, '
                            f'{candidates_count} candidates, '
                            f'{votes_count} votes, '
                            f'{thermo_count} thermo matches'
                        )
                    )
                    total_synced += 1
                else:
                    error_msg = result.get('error', 'Unknown error')
                    self.stdout.write(self.style.ERROR(f'  ❌ Failed: {error_msg}'))
                    total_failed += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Exception: {str(e)}'))
                logger.exception(f'Error syncing job {job.name}')
                total_failed += 1
            
            self.stdout.write('')  # Blank line
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SYNC SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'✅ Synced:  {total_synced} job(s)')
        self.stdout.write(f'⏭️  Skipped: {total_skipped} job(s) (too soon)')
        self.stdout.write(f'❌ Failed:  {total_failed} job(s)')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 This was a dry run - no actual changes made'))
