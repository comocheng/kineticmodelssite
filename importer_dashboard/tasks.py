"""
Celery tasks for running RMG import jobs locally.

Replaces the SLURM submission in SSHJobManager.start_job().
The import logic mirrors what import.sh did on the cluster.
"""
import os
import shlex
import subprocess
import signal
import logging
import json
from pathlib import Path
from datetime import datetime

from celery import shared_task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from .importer_files import (EXIT_KILLED_FROM_WEB_PAGE, apply_progress, clear_importer_state,
                             read_importer_state, read_progress, reset_progress)
from . import species_sync
from .job_logs import keep_logs, kept_path, logs_folder
from .job_paths import job_folder
from .port_allocator import NoFreePortError, apply_port_to_command, release_port, reserve_port

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='importer_dashboard.run_import_job')
def run_import_job(self, job_id):
    """
    Run an RMG import job locally via Celery.

    This replaces:
      - SSHJobManager.start_job() (which ran sbatch on the cluster)
      - The import.sh SLURM script

    The job's status, counts and log are written here only while the job still has the status
    this task gave it: the Kill button and refresh_statuses also change statuses, and a full save
    of the job object read at the start would put back the counts and status of that moment.

    Args:
        job_id: ID of the ClusterJob to run
    """
    # Import here to avoid circular imports
    from importer_dashboard.models import ClusterJob, ImportJobStatus, JobLog

    try:
        job = ClusterJob.objects.get(id=job_id)
    except ClusterJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return {'status': 'error', 'message': f'Job {job_id} not found'}

    # Store the Celery task ID on the job (replaces slurm_job_id)
    job.celery_task_id = self.request.id
    job.status = ImportJobStatus.RUNNING
    job.host = 'localhost'
    job.started_at = timezone.now()
    job.completed_at = None
    job.worker_pid = None  # the previous run's PID, until Popen below sets this run's
    job.save(update_fields=['celery_task_id', 'status', 'host', 'started_at', 'completed_at',
                            'worker_pid', 'updated_at'])
    reset_progress(job)

    JobLog.objects.create(
        job=job,
        log_type='info',
        message=f'Import job started via Celery (task: {self.request.id})'
    )

    rmg_py_path = getattr(settings, 'RMG_PY_PATH', '/path/to/RMG-Py')
    conda_env = getattr(settings, 'CONDA_ENV_NAME', 'rmg_env')
    conda_base = getattr(settings, 'CONDA_BASE_PATH', '/home/prometheus/miniconda3')
    job_path = job_folder(job)
    # In the job's own log folder, which outlives a draft's worktree (job_logs.py)
    output_log = kept_path(job, 'output.log')
    error_log = kept_path(job, 'error.log')

    def finish(status, log_type, message, result):
        """Record how this run ended, unless someone else (the Kill button) already did."""
        if _set_final_status(job, status):
            apply_progress(job, read_progress(job_path))
            JobLog.objects.create(job=job, log_type=log_type, message=message)
        commit_identifications(job, final=True)
        _keep_logs(job)
        species_sync.queue(job, force=True)  # the job page's species rows, from the vote database
        return {'job_id': job_id, **result}

    poll_seconds = getattr(settings, 'IMPORTER_STATE_POLL_SECONDS', 10)
    process = None
    detached = False  # set when the importer is left running without this task
    reserved = False
    try:
        clear_importer_state(job_path)

        # Parse the actual import.sh to get the correct command for this mechanism.
        # Each import.sh has different filenames (species, thermo, reactions, etc.)
        try:
            command = _build_command_from_import_sh(os.path.join(job_path, 'import.sh'),
                                                    rmg_py_path, conda_env, job_path)
        except (OSError, ValueError) as e:
            logger.error(f"Could not read import.sh of {job.name}: {e}")
            return finish(ImportJobStatus.FAILED, 'error', f'Could not read import.sh: {e}',
                          {'status': 'error', 'error': str(e)})

        # Reserve a free port for this run instead of the one hard-coded in import.sh
        try:
            port = reserve_port(job)
            reserved = True
        except NoFreePortError as e:
            # Every port is busy: put the job back in the queue and try again later
            ClusterJob.objects.filter(pk=job.pk, status=ImportJobStatus.RUNNING).update(
                status=ImportJobStatus.PENDING)
            JobLog.objects.create(job=job, log_type='warning',
                                  message=f'{e}; retrying in 5 minutes')
            raise self.retry(countdown=300, max_retries=None)
        command = apply_port_to_command(command, port)

        logger.info(f"Starting import for {job.name} at {job_path}")
        logger.info(f"Command: {command}")

        conda_bin = os.path.join(conda_base, 'envs', conda_env, 'bin')
        proc_env = {
            **os.environ,
            'PYTHONPATH': rmg_py_path,
            'RMG': rmg_py_path,
            'PATH': f'{conda_bin}:{os.environ.get("PATH", "")}',
            # Write output.log as the importer prints, so the Output log page follows the run
            'PYTHONUNBUFFERED': '1',
        }
        evidence_index = getattr(settings, 'IMPORTER_EVIDENCE_INDEX', '')
        if evidence_index:
            # The RMG-database libraries and earlier imports vote too (the importer carries on
            # without them if the index hasn't been built yet)
            proc_env['RMG_EVIDENCE_INDEX'] = evidence_index

        os.makedirs(logs_folder(job), exist_ok=True)
        with open(output_log, 'w') as stdout_f, open(error_log, 'w') as stderr_f:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=job_path,
                preexec_fn=os.setsid,  # Create process group for clean kill
                env=proc_env,
            )

            # Store PID for potential cancellation
            job.worker_pid = process.pid
            job.save(update_fields=['worker_pid'])

            # Wait for the importer to exit, or to start waiting for someone to confirm a
            # match on its page. Then it has nothing to compute, so free this worker slot
            # for other jobs and leave it running; refresh_statuses takes over from there.
            returncode = None
            while returncode is None:
                try:
                    returncode = process.wait(timeout=poll_seconds)
                except subprocess.TimeoutExpired:
                    # Each identification goes into the draft's branch within a minute
                    commit_identifications(job)
                    if read_importer_state(job_path).get('state') == 'awaiting_input':
                        detached = True
                        break

        if detached:
            commit_identifications(job, final=True)
            if _set_final_status(job, ImportJobStatus.AWAITING_INPUT):
                apply_progress(job, read_progress(job_path))
                JobLog.objects.create(
                    job=job,
                    log_type='info',
                    message=('Waiting for someone to confirm a match on the importer page. The importer '
                             'keeps running and keeps its port; its worker slot is free for other jobs.')
                )
            logger.info(f"Job {job.name} is awaiting input; freed its worker slot")
            return {'status': 'awaiting_input', 'job_id': job_id}

        if returncode == EXIT_KILLED_FROM_WEB_PAGE:
            return finish(ImportJobStatus.CANCELLED, 'info',
                          'Stopped with the Kill job button on the importer page',
                          {'status': 'cancelled'})

        if returncode == 0:
            logger.info(f"Job {job.name} completed successfully")
            return finish(ImportJobStatus.COMPLETED, 'info', 'Import job completed successfully',
                          {'status': 'completed'})

        reason = ''
        if returncode < 0:
            # Negative code = killed by signal; -9 on a big job is usually the OOM killer
            reason = f' (killed by signal {-returncode}{", likely out of memory" if returncode == -9 else ""})'
        logger.error(f"Job {job.name} failed with exit code {returncode}")
        return finish(
            ImportJobStatus.FAILED, 'error',
            (f'Job failed with exit code {returncode}{reason}.\n'
             f'error.log:\n{_tail_file(error_log, 20)}\n\noutput.log:\n{_tail_file(output_log, 20)}'),
            {'status': 'failed', 'returncode': returncode})

    except SoftTimeLimitExceeded:
        logger.warning(f"Job {job.name} hit time limit")
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        return finish(ImportJobStatus.FAILED, 'error', 'Job exceeded time limit and was terminated',
                      {'status': 'timeout'})

    except Retry:
        raise

    except Exception as e:
        logger.exception(f"Job {job.name} encountered an error: {e}")
        if process and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        return finish(ImportJobStatus.FAILED, 'error', f'Unexpected error: {e}',
                      {'status': 'error', 'error': str(e)})

    finally:
        if reserved and not detached:
            release_port(job)  # a detached importer still serves its page on this port
        if process is not None and not detached:
            schedule_evidence_index_refresh()  # the import has rewritten its model's libraries


def _keep_logs(job):
    """Keep the run's RMG.log in the job's log folder; a failure to copy must not change the run's end."""
    try:
        keep_logs(job)
    except OSError as e:
        logger.warning(f"Could not keep the logs of {job.name}: {e}")


def _set_final_status(job, status):
    """
    Give the job the status this run ended with, but only if it still has a status that this
    run set (Running, or Pending while it waited for a port). The Kill button sets Cancelled,
    and that must stay. Returns True if the status was set.
    """
    from importer_dashboard.models import ClusterJob, ImportJobStatus

    fields = {'status': status, 'updated_at': timezone.now()}
    if status != ImportJobStatus.AWAITING_INPUT:
        fields['completed_at'] = timezone.now()
    changed = ClusterJob.objects.filter(
        pk=job.pk, status__in=[ImportJobStatus.RUNNING, ImportJobStatus.PENDING]).update(**fields)
    if changed:
        for name, value in fields.items():
            setattr(job, name, value)
    return bool(changed)


def _build_command_from_import_sh(import_sh_path, rmg_py_path, conda_env, job_path):
    """
    Parse import.sh and build a local command from it.

    Each mechanism's import.sh has different filenames and flags. Example:

        python -m cProfile -o importChemkin.profile $RMGpy/importChemkin.py \\
            --species hfcmech_v448a.txt \\
            --reactions hfcmech_v448a.txt \\
            --thermo thermo-hfo1234zee-burcat-c.txt \\
            --known SMILES.txt \\
            --port 8179

    This function:
    1. Reads import.sh
    2. Strips SLURM headers (#SBATCH), comments, blank lines, and the
       cProfile/gprof2dot wrapper
    3. Extracts the actual importChemkin.py invocation with all its args
    4. Replaces $RMGpy with the real path
    5. Wraps it with conda activation

    Returns a shell command string ready for subprocess.
    """
    import re

    if not os.path.exists(import_sh_path):
        raise FileNotFoundError(
            f"import.sh not found at {import_sh_path}. "
            f"Cannot determine the correct command for this mechanism."
        )

    with open(import_sh_path, 'r') as f:
        raw_content = f.read()

    # Join continuation lines (backslash + newline)
    content = raw_content.replace('\\\n', ' ')

    # Find the line that runs importChemkin.py
    import_cmd = None
    for line in content.splitlines():
        stripped = line.strip()

        # Skip empty lines, shebangs, SBATCH directives, comments
        if not stripped or stripped.startswith('#'):
            continue

        # Skip gprof2dot post-processing line
        if 'gprof2dot' in stripped:
            continue

        # This is the importChemkin command (possibly wrapped in cProfile)
        if 'importChemkin' in stripped:
            import_cmd = stripped
            break

    if not import_cmd:
        raise ValueError(
            f"Could not find importChemkin.py command in {import_sh_path}. "
            f"File contents:\n{raw_content[:500]}"
        )

    # Strip cProfile wrapper: "python -m cProfile -o importChemkin.profile $RMGpy/importChemkin.py ..."
    # becomes:                 "python $RMGpy/importChemkin.py ..."
    import_cmd = re.sub(
        r'python\s+-m\s+cProfile\s+-o\s+\S+\s+',
        'python ',
        import_cmd
    )

    # Replace $RMGpy or ${RMGpy} with the actual path
    import_cmd = import_cmd.replace('$RMGpy', rmg_py_path)
    import_cmd = import_cmd.replace('${RMGpy}', rmg_py_path)
    import_cmd = import_cmd.replace('$RMG', rmg_py_path)
    import_cmd = import_cmd.replace('${RMG}', rmg_py_path)

    # Collapse multiple spaces
    import_cmd = re.sub(r'\s+', ' ', import_cmd).strip()

    # The python of the importers' conda environment (settings.CONDA_BASE_PATH), not the one on PATH
    conda_python = os.path.join(getattr(settings, 'CONDA_BASE_PATH', '/home/prometheus/miniconda3'),
                                'envs', conda_env, 'bin', 'python')
    import_cmd = re.sub(r'^python\b', lambda _: shlex.quote(conda_python), import_cmd)

    # Wrap with conda activation and cd
    # stderr is left alone so Popen routes it to error.log (the Errors page)
    # The path is quoted because the command runs in a shell, and some model folders
    # have shell characters in their names, e.g. PCI2017/038-Labbe-Zhao(30Torr-10Atm)
    command = (
        f'cd {shlex.quote(job_path)} && '
        f'{import_cmd}'
    )

    logger.info(f"Built command from import.sh: {command}")
    return command


def _update_completion_stats(job, job_path):
    """Copy the importer's final progress counts (its progress.json) onto the job."""
    try:
        if not apply_progress(job, read_progress(job_path)):
            logger.warning(f"No progress.json for {job.name}, so its final counts weren't recorded")
    except Exception as e:
        logger.warning(f"Could not read completion stats: {e}")


def _tail_file(filepath, lines=20):
    """Read last N lines of a file."""
    try:
        with open(filepath, 'r') as f:
            return '\n'.join(f.readlines()[-lines:])
    except Exception:
        return '(could not read file)'

@shared_task(name='importer_dashboard.refresh_all_job_statuses')
def refresh_all_job_statuses():
    """Periodic task to update status of all active jobs."""
    from .local_job_manager import LocalJobManager
    from .models import ImportJobConfig
    
    config = ImportJobConfig.objects.filter(is_default=True).first()
    if config:
        manager = LocalJobManager(config=config)
        manager.refresh_statuses()


def schedule_evidence_index_refresh():
    """Queue refresh_evidence_index, if the evidence index is turned on."""
    if getattr(settings, 'IMPORTER_EVIDENCE_INDEX', ''):
        refresh_evidence_index.delay()


@shared_task(name='importer_dashboard.refresh_evidence_index')
def refresh_evidence_index():
    """
    Bring the evidence index up to date: re-read the RMG-database and RMG-models libraries whose
    files changed since the last build. The first run builds the whole index (about a minute);
    after that a refresh takes seconds, so it runs after every import, which rewrites that
    model's libraries, and once a night for RMG-database updates. It runs evidence_index.py in
    the importers' conda environment, because reading the libraries needs RMG.
    """
    index = getattr(settings, 'IMPORTER_EVIDENCE_INDEX', '')
    if not index:
        return {'status': 'disabled'}
    rmg_py_path = getattr(settings, 'RMG_PY_PATH', '/path/to/RMG-Py')
    python = os.path.join(getattr(settings, 'CONDA_BASE_PATH', '/home/prometheus/miniconda3'), 'envs',
                          getattr(settings, 'CONDA_ENV_NAME', 'rmg_env'), 'bin', 'python')
    command = [python, os.path.join(rmg_py_path, 'evidence_index.py'), 'refresh', '--index', index,
               '--database', os.path.join(getattr(settings, 'RMG_DATABASE_PATH', ''), 'input'),
               '--models', getattr(settings, 'RMG_MODELS_PATH', '')]
    try:
        result = subprocess.run(command, cwd=rmg_py_path, capture_output=True, text=True, timeout=3600,
                                env={**os.environ, 'PYTHONPATH': rmg_py_path})
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error(f"Could not refresh the evidence index: {e}")
        return {'status': 'failed', 'error': str(e)}
    summary = (result.stderr.strip().splitlines() or [''])[-1]
    if result.returncode != 0:
        logger.error(f"Refreshing the evidence index failed:\n{result.stderr[-2000:]}")
        return {'status': 'failed', 'error': result.stderr[-2000:]}
    logger.info(summary)
    return {'status': 'ok', 'summary': summary}


@shared_task(name='importer_dashboard.sync_job_species')
def sync_job_species(job_id):
    """Fill the job's species rows from its vote database (importer_dashboard/species_sync.py)."""
    from .models import ClusterJob
    job = ClusterJob.objects.filter(pk=job_id).select_related('draft', 'config').first()
    if job is None:
        return None
    result = species_sync.sync(job)
    if result is None:
        return {'job_id': job_id, 'skipped': 'another sync of this job is running'}
    return {'job_id': job_id, **{key: result.get(key) for key in ('success', 'identified_synced', 'candidates_synced', 'error')}}


@shared_task(name='importer_dashboard.sync_rmg_models_read_copy')
def sync_rmg_models_read_copy(reason='schedule'):
    """
    Fast-forward the read copy of RMG-models to GitHub's master, when that is safe
    (importer_dashboard/read_copy_sync.py). The GitHub webhook queues it on a push to master,
    and Celery Beat every 15 minutes.
    """
    from .read_copy_sync import sync
    return sync(reason)


@shared_task(name='importer_dashboard.close_merged_draft')
def close_merged_draft(draft_id):
    """
    Read the state of a draft's pull request now, with the token of the person who pushed it: a
    merged one deletes the draft's branch on GitHub and closes the draft
    (github.refresh_pull_request). The GitHub webhook queues it when a pull request is merged.
    """
    from . import github
    from .models import Draft
    draft = Draft.objects.filter(pk=draft_id).first()
    if draft is None or not draft.is_open:
        return {'draft_id': draft_id, 'skipped': 'the draft is closed'}
    draft = github.refresh_pull_request(draft, max_age=0)
    return {'draft_id': draft_id, 'status': draft.status, 'pr_state': draft.pr_state}


@shared_task(name='importer_dashboard.ping')
def ping(sent_at=None):
    """Lightweight probe used to measure enqueue -> worker-pickup latency.

    Returns the worker-side monotonic clock reading at the moment the task
    starts executing. On a single host time.monotonic() shares a system-wide
    reference, so the caller can subtract its own send-time monotonic reading to
    obtain the real start-up latency of the co-located Celery/Redis worker pool.
    """
    import time
    return time.monotonic()


def commit_identifications(job, final=False):
    """Commit the job's identifications to its draft (drafts.checkpoint_job); never raises."""
    if getattr(job, 'draft_id', None) is None:
        return None
    from .drafts import checkpoint_job
    try:
        return checkpoint_job(job, final=final)
    except Exception:
        logger.exception(f"Could not commit the identifications of {job.name}")
        return None


@shared_task(name='importer_dashboard.reload_changed_models')
def reload_changed_models(old, new):
    """
    Reload into the database the models whose folders changed when the read copy moved from old
    to new (importer_dashboard/model_reload.py). read_copy_sync.sync queues it after a fast-forward.
    """
    from .model_reload import reload_changed
    return [{'model': r.model_name, 'status': r.status, 'message': r.message} for r in reload_changed(old, new)]


@shared_task(name='importer_dashboard.apply_model_reload')
def apply_model_reload(reload_id, user_id=None):
    """Apply on the Settings page: run a held reload again and keep it, then update the keys."""
    from .model_reload import reload, update_keys
    from .models import ModelReload
    record = ModelReload.objects.get(pk=reload_id)
    record.applied_by_id = user_id
    reload(record, force=True)
    if record.status == ModelReload.Status.APPLIED:
        update_keys()
    return {'model': record.model_name, 'status': record.status, 'message': record.message}
