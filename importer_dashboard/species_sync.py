"""
Fill a job's species rows (the Species, identifications and votes lists of its page) from its vote
database, votes_<hash>.db in the model folder, with incremental_sync.IncrementalSync.

Only Update progress used to do this, and only for jobs that were running, so a job that finished
while nobody pressed it (ANL-Brown, Nov 2026) had its counts, which come from progress.json, but
no species rows. Now a sync is queued:

- when a run ends (tasks.run_import_job and LocalJobManager._record_end);
- every 5 minutes while a job is running or awaiting input (LocalJobManager.refresh_statuses);
- when a job page has no species rows but the job has a vote database (views.job_detail).
"""
import fcntl
import logging
import os
from contextlib import contextmanager
from datetime import timedelta
from glob import glob

from django.utils import timezone

from .job_logs import logs_folder
from .job_paths import job_folder, jobs_on_this_machine

logger = logging.getLogger(__name__)

SYNC_EVERY_SECONDS = 300


def vote_databases(job):
    """The vote databases in the job's model folder (in its open draft, if it has one)."""
    return glob(os.path.join(job_folder(job), 'votes_*.db'))


def tried_recently(job, seconds=SYNC_EVERY_SECONDS):
    """True if a sync of `job` ran in the last `seconds` (whether or not it worked)."""
    since = timezone.now() - timedelta(seconds=seconds)
    return job.sync_logs.filter(sync_type='incremental', synced_at__gte=since).exists()


def queue(job, force=False):
    """
    Queue a sync of the job's species rows, unless one ran in the last 5 minutes (`force` skips
    that wait, for the end of a run). Returns True if a sync was queued.
    """
    if not jobs_on_this_machine() or not vote_databases(job):
        return False
    if not force and tried_recently(job):
        return False
    from .tasks import sync_job_species
    try:
        sync_job_species.delay(job.pk)
    except Exception as e:  # the broker is down; the next refresh or page view queues it again
        logger.warning(f'Could not queue the species sync of {job.name}: {e}')
        return False
    return True


@contextmanager
def _only_one(job):
    """True while this process holds the job's sync lock; False if another sync of it runs."""
    os.makedirs(logs_folder(job), exist_ok=True)
    with open(os.path.join(logs_folder(job), '.species-sync.lock'), 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def sync(job):
    """
    Copy the job's vote database into its species rows now (in a Celery worker). Returns the
    result of IncrementalSync, or None if another sync of this job is running.
    """
    from .incremental_sync import sync_job_votes
    from .local_job_manager import LocalJobManager
    from .models import ImportJobConfig, SyncLog

    with _only_one(job) as alone:
        if not alone:
            return None
        manager = LocalJobManager(config=job.config or ImportJobConfig.objects.filter(is_default=True).first())
        started = timezone.now()
        result = sync_job_votes(job, ssh_manager=manager)
        if not result.get('success') and not job.sync_logs.filter(synced_at__gte=started).exists():
            # So a failing sync waits 5 minutes before the next try, like a working one
            SyncLog.objects.create(job=job, sync_type='incremental', success=False,
                                   error_message=str(result.get('error') or '')[:2000])
            logger.warning(f'Species sync of {job.name} failed: {result.get("error")}')
        return result
