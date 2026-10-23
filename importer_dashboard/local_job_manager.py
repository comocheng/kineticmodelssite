"""
Local job manager that replaces SSHJobManager for office-server deployments.

Instead of SSH + SLURM, this uses Celery for task execution and reads
log files directly from the local filesystem.

API parity with SSHJobManager — every public method that views.py or
incremental_sync.py calls on SSHJobManager exists here so the manager
factory can swap them transparently.
"""
import os
import re
import signal
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone
from celery.result import AsyncResult

from .models import ClusterJob, ImportJobConfig, ImportJobStatus, JobLog
from .tasks import run_import_job, schedule_evidence_index_refresh, _tail_file
from .importer_files import apply_progress, is_process_alive, read_importer_state, read_progress
from .port_allocator import release_port, release_stale_ports

# Statuses whose importer may still be running, and so still holds its port
ACTIVE_STATUSES = [ImportJobStatus.RUNNING, ImportJobStatus.PENDING, ImportJobStatus.AWAITING_INPUT]

logger = logging.getLogger(__name__)


class LocalJobManager:
    """
    Manages import jobs running locally via Celery.
    Drop-in replacement for SSHJobManager.
    """

    def __init__(self, config: ImportJobConfig = None):
        self.config = config
        self.root_path = getattr(settings, 'RMG_MODELS_PATH',
                                 config.root_path if config else '/tmp')

    def connect(self):
        """No-op for local execution (no SSH needed)."""
        pass

    def disconnect(self):
        """No-op for local execution."""
        pass

    def is_connected(self):
        """Always True for local execution."""
        return True

    def discover_jobs(self):
        """
        Discover import jobs from local filesystem.
        Replaces SSHJobManager.discover_jobs() which used SSH ls commands.

        A model is a folder with an import.sh, either directly under the root
        (e.g. ANL-Brown, named the way SSHJobManager names it) or one level down
        (e.g. CombFlame2013/1315-Chang).
        """
        root = Path(self.root_path)
        discovered = []

        if not root.exists():
            logger.error(f"Root path does not exist: {self.root_path}")
            return discovered

        model_dirs = []
        for journal_dir in sorted(root.iterdir()):
            if not journal_dir.is_dir() or journal_dir.name.startswith('.'):
                continue
            if (journal_dir / 'import.sh').exists():
                model_dirs.append((journal_dir.name, journal_dir))
            for model_dir in sorted(journal_dir.iterdir()):
                if model_dir.is_dir() and (model_dir / 'import.sh').exists():
                    model_dirs.append((f"{journal_dir.name}/{model_dir.name}", model_dir))

        for job_name, model_dir in model_dirs:
            discovered.append(job_name)

            # Create ClusterJob if it doesn't exist
            job, created = ClusterJob.objects.get_or_create(
                name=job_name,
                defaults={
                    'status': ImportJobStatus.IDLE,
                    'config': self.config,
                }
            )
            if created:
                # Parse port from import.sh. It is only a hint now (the port
                # allocator reserves one at start), so skip a port another job in
                # this config already holds rather than violate the unique constraint.
                port = self._parse_port(model_dir / 'import.sh')
                if port and not ClusterJob.objects.filter(
                        config=job.config, port=port).exclude(pk=job.pk).exists():
                    job.port = port
                    job.save()
                logger.info(f"Discovered new job: {job_name}")

        return discovered

    def _parse_port(self, import_sh_path):
        """Extract port number from import.sh file."""
        try:
            content = import_sh_path.read_text()
            # Match both LSF and SLURM formats
            for line in content.split('\n'):
                match = re.search(r'port(\d+)', line)
                if match:
                    return int(match.group(1))
                match = re.search(r'--port\s+(\d+)', line)
                if match:
                    return int(match.group(1))
        except Exception as e:
            logger.warning(f"Could not parse port from {import_sh_path}: {e}")
        return None

    def start_job(self, job: ClusterJob):
        """
        Start an import job via Celery.
        Replaces SSHJobManager.start_job() which used sbatch.
        
        Returns (task_id, host) to match the SLURM interface.
        """
        result = run_import_job.delay(job.id)

        job.celery_task_id = result.id
        job.status = ImportJobStatus.PENDING
        job.worker_pid = None  # the previous run's PID would make the job look alive
        job.save()

        logger.info(f"Submitted Celery task {result.id} for job {job.name}")
        return result.id, 'localhost'

    def kill_job(self, job: ClusterJob):
        """
        Kill a running job.
        Replaces SSHJobManager.kill_job() which used scancel.
        """
        # First, revoke the Celery task
        if job.celery_task_id:
            from kms.celery import app
            app.control.revoke(job.celery_task_id, terminate=True, signal='SIGTERM')
            logger.info(f"Revoked Celery task {job.celery_task_id}")

        # Also kill the subprocess if it's running
        if job.worker_pid:
            try:
                os.killpg(os.getpgid(job.worker_pid), signal.SIGTERM)
                logger.info(f"Killed process group {job.worker_pid}")
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"Could not kill PID {job.worker_pid}: {e}")

        job.status = ImportJobStatus.CANCELLED
        job.completed_at = timezone.now()
        job.save()
        release_port(job)

    def get_log_tail(self, job: ClusterJob, lines: Optional[int] = 50):
        """
        Read RMG.log tail, or the complete log when lines is None.
        Replaces SSHJobManager.get_log_tail() which used SSH.
        """
        log_path = os.path.join(self.root_path, job.name, 'RMG-Py-output', 'RMG.log')
        return self._tail_local_file(log_path, lines)

    def get_console_output(self, job: ClusterJob):
        """Read output.log from local filesystem."""
        log_path = os.path.join(self.root_path, job.name, 'output.log')
        return self._read_local_file(log_path)

    def get_error_log(self, job: ClusterJob):
        """Read error.log from local filesystem."""
        log_path = os.path.join(self.root_path, job.name, 'error.log')
        return self._read_local_file(log_path)

    def get_completion_stats(self, job: ClusterJob):
        """The importer's progress counts (its progress.json), or None."""
        return read_progress(os.path.join(self.root_path, job.name))

    def get_live_progress(self, job: ClusterJob):
        """
        Read progress.json for a running job.
        Replaces fetching from OOD URL or localhost tunnel.
        """
        return self.get_completion_stats(job)

    def refresh_statuses(self):
        """
        Update the status of active jobs. Jobs that have a Celery task are checked
        against Celery; jobs awaiting input, whose task has already freed its worker
        slot, are checked against their importer process.
        Replaces update_running_jobs_status() which parsed squeue output.
        """
        active_jobs = ClusterJob.objects.filter(
            status__in=[ImportJobStatus.RUNNING, ImportJobStatus.PENDING],
            celery_task_id__isnull=False
        )

        for job in active_jobs:
            result = AsyncResult(job.celery_task_id)
            new_status, fields = job.status, {}

            if result.state in ('PENDING', 'RETRY'):
                # Celery also answers PENDING for a task it has no record of, e.g. once
                # the result has expired, so trust a live importer over it. RETRY means
                # the task is waiting for a free port, before any importer starts.
                if not (job.status == ImportJobStatus.RUNNING and self._is_pid_running(job.worker_pid)):
                    new_status = ImportJobStatus.PENDING
            elif result.state == 'STARTED':
                if job.worker_pid and not self._is_pid_running(job.worker_pid):
                    new_status = ImportJobStatus.FAILED
                    fields['completed_at'] = timezone.now()
                    logger.warning(
                        f"Marking job {job.name} as failed: worker PID {job.worker_pid} is not running"
                    )
                else:
                    new_status = ImportJobStatus.RUNNING
            elif result.state == 'SUCCESS':
                new_status = ImportJobStatus.COMPLETED
                fields['completed_at'] = timezone.now()
            elif result.state in ('FAILURE', 'REVOKED'):
                new_status = ImportJobStatus.FAILED
                fields['completed_at'] = timezone.now()

            self._set_status(job, new_status, **fields)

        for job in ClusterJob.objects.filter(status=ImportJobStatus.AWAITING_INPUT):
            self._refresh_detached_job(job)

        # A worker killed mid-job never reaches its `finally`, so sweep up here
        release_stale_ports(ACTIVE_STATUSES)

    def _set_status(self, job, new_status, **fields):
        """
        Change a job's status, but only if it still has the status we read. The Celery
        task and the Kill button also change statuses, and this must not overwrite them.
        Returns True if the status was changed.
        """
        if new_status == job.status:
            return False
        changed = ClusterJob.objects.filter(pk=job.pk, status=job.status).update(status=new_status, **fields)
        if changed:
            job.status = new_status
            for name, value in fields.items():
                setattr(job, name, value)
        return bool(changed)

    def _refresh_detached_job(self, job):
        """
        Check on an importer left running, awaiting input, after its Celery task freed
        its worker slot. Once it exits, record why, using the state it last reported.
        """
        job_path = os.path.join(self.root_path, job.name)
        state = read_importer_state(job_path)
        if self._importer_alive(job, state):
            apply_progress(job, read_progress(job_path))
            return

        last_state = state.get('state')
        if last_state == 'finished':
            new_status, log_type, message = ImportJobStatus.COMPLETED, 'info', 'Import job completed successfully'
        elif last_state == 'stopped':
            new_status, log_type, message = (ImportJobStatus.CANCELLED, 'info',
                                             'Stopped with the Kill job button on the importer page')
        else:
            if state.get('error'):
                reason = f": {state['error']}"
            elif last_state:
                reason = f" (the last thing it reported was {last_state!r})"
            else:
                reason = ''
            new_status, log_type = ImportJobStatus.FAILED, 'error'
            message = (f'The importer stopped unexpectedly while awaiting input{reason}.\n'
                       f'error.log:\n{_tail_file(os.path.join(job_path, "error.log"), 20)}\n\n'
                       f'output.log:\n{_tail_file(os.path.join(job_path, "output.log"), 20)}')

        if self._set_status(job, new_status, completed_at=timezone.now()):
            apply_progress(job, read_progress(job_path))
            JobLog.objects.create(job=job, log_type=log_type, message=message)
            release_port(job)
            schedule_evidence_index_refresh()  # the import has rewritten its model's libraries
            logger.info(f"Job {job.name} ended while awaiting input: {new_status}")

    def _importer_alive(self, job, state):
        """Is this job's importer still running? Prefers the PID the importer reported itself."""
        return self._is_pid_running(state.get('pid') or job.worker_pid)

    # ------------------------------------------------------------------
    # Aliases so views.py can call the same names as SSHJobManager
    # ------------------------------------------------------------------

    def update_running_jobs_status(self):
        """Alias for refresh_statuses() — matches SSHJobManager API."""
        return self.refresh_statuses()

    def get_progress_json(self, job: ClusterJob):
        """
        Read progress.json for a job (running or completed).
        Matches SSHJobManager.get_progress_json() signature.
        """
        return read_progress(os.path.join(self.root_path, job.name))

    def refresh_all_progress(self):
        """
        Refresh progress for all running jobs, and jobs awaiting input, from their
        local progress.json files.
        Matches SSHJobManager.refresh_all_progress() return signature.
        Returns the count of jobs updated.
        """
        running_jobs = ClusterJob.objects.filter(
            status__in=[ImportJobStatus.RUNNING, ImportJobStatus.AWAITING_INPUT]
        ).exclude(host=None)

        updated = 0
        for job in running_jobs:
            if apply_progress(job, self.get_progress_json(job)):
                updated += 1
        return updated

    def exec_command(self, command: str):
        """
        Run a shell command locally.
        Matches SSHJobManager.exec_command() return signature: (stdout, stderr).
        """
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=120
            )
            return result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return '', 'Command timed out after 120 seconds'
        except Exception as e:
            return '', str(e)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_local_file(self, path, max_bytes=5_000_000):
        """Read a local file, capped at max_bytes."""
        try:
            with open(path, 'r') as f:
                return f.read(max_bytes)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return None

    def _tail_local_file(self, path, lines=50):
        """Read last N lines of a local file, or all content when lines is None."""
        try:
            with open(path, 'r') as f:
                if lines is None:
                    return f.read()
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Could not tail {path}: {e}")
            return None

    def _is_pid_running(self, pid):
        """
        Return True if `pid` is a running importer: not a zombie, and (on Linux) not
        a reused PID belonging to some other program.
        """
        return is_process_alive(pid, expect_in_cmdline='importChemkin')
