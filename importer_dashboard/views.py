"""
Views for the RMG Importer Dashboard

Provides web interface for managing import jobs on the cluster.
"""

from django.shortcuts import render, redirect, get_object_or_404
from kms.access import actor_name, site_login_required, superuser_required, write_login_required
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Case, Count, When, Value, IntegerField, OuterRef, Q, Subquery
import json
import logging
import os
from django.conf import settings

from .models import ClusterJob, DraftStatus, ImportJobConfig, JobLog, ImportJobStatus, VotingReaction
from .manager_factory import get_job_manager
from .logger import dashboard_logger, setup_dashboard_logging
from .importer_files import apply_progress
from .job_logs import LOGS, log_path, read_log
from .job_paths import is_model_folder, job_folder, jobs_on_this_machine, model_folder_names
from . import drafts, editor, github

# Jobs whose importer is up, so its page can be opened and its progress changes
LIVE_STATUSES = [ImportJobStatus.RUNNING, ImportJobStatus.AWAITING_INPUT]

# Set up dashboard logging - this forwards Python logging to dashboard_logger
logger = setup_dashboard_logging('importer_dashboard', 'dashboard')

# Also create a standard logger for non-dashboard messages (console/file logs)
# But note: dashboard_logger is the one that shows in the Activity Log UI
# logger is for standard Python logging (console, files, etc.)
standard_logger = logging.getLogger(__name__)


def latest_error(job):
    """The message of the job's latest error in its log, or None."""
    entry = job.logs.filter(log_type='error').order_by('-timestamp').first()
    return entry.message if entry else None


def model_jobs(jobs):
    """
    The jobs of `jobs` that are models: their folder in RMG-models has an import.sh, or they have
    an open draft (a model added on the create page is only in its draft). Folders such as
    modelComparer, translations or a journal folder (CombFlame2013) are not jobs. When the jobs run
    on a cluster, their folders are not on this server, so all jobs are given.
    """
    names = model_folder_names() if jobs_on_this_machine() else None
    if names is None:
        return jobs
    return jobs.filter(Q(name__in=names) | Q(draft__status=DraftStatus.OPEN))


def not_a_model(job):
    """True if the job's folder is on this server and has no import.sh, so there is nothing to import."""
    if not jobs_on_this_machine() or (job.draft_id and job.draft.is_open):
        return False
    return not is_model_folder(job_folder(job))


def attach_draft(request, job):
    """
    Open the draft of the job's model (or use the open one) before the job starts, so the job
    runs in its worktree and its identifications are committed to its branch. Returns True when
    the job has a draft, None when drafts are off, and False (after a message) when the draft
    could not be opened: then the job must not start in the read copy.
    """
    if getattr(settings, 'IMPORTER_MODE', 'cluster') != 'local' or not drafts.drafts_enabled():
        return None
    try:
        draft, warning = drafts.open_draft(job.name, user=request.user)
    except drafts.DraftError as e:
        messages.error(request, f'Could not open a draft of {job.name} in RMG-models: {e}')
        return False
    if job.draft_id != draft.pk:
        ClusterJob.objects.filter(pk=job.pk).update(draft=draft)
        job.draft = draft
    if warning:
        messages.warning(request, warning)
    return True


@site_login_required
def dashboard_index(request):
    """
    Main dashboard view showing all import jobs
    """
    # Get or create default configuration
    config, created = ImportJobConfig.objects.get_or_create(
        is_default=True,
        defaults={
            'name': "Default Explorer Configuration",
            'ssh_host': 'login.explorer.northeastern.edu',
            'ssh_port': 22,
            'root_path': '/projects/westgroup/lekia.p/Importer/RMG-models/',
            'slurm_partition': 'west',
            'slurm_time_limit': '3-00:00:00',
            'slurm_memory': '32768M',
            'conda_env_name': 'rmg_env',
            'rmg_py_path': '/projects/westgroup/lekia.p/RMG/RMG-Py',
        }
    )

    # Keep statuses fresh so stale local/Celery jobs don't appear as running.
    if config:
        try:
            manager = get_job_manager(config=config)
            manager.update_running_jobs_status()
        except Exception as exc:
            logger.warning(f"Could not refresh job statuses on dashboard load: {exc}")

    # The jobs that are models, ordered with running jobs first, then alphabetically by name.
    # A failed job carries the first line of its latest error, so the row says why.
    listed = model_jobs(ClusterJob.objects.all())
    jobs = listed.annotate(
        last_error=Subquery(JobLog.objects.filter(job=OuterRef('pk'), log_type='error')
                            .order_by('-timestamp').values('message')[:1]),
        status_priority=Case(
            When(status__in=LIVE_STATUSES, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('status_priority', 'name')

    # Handle search query
    search_query = request.GET.get('q', '').strip()
    if search_query:
        jobs = jobs.filter(
            Q(name__icontains=search_query) |
            Q(host__icontains=search_query) |
            Q(slurm_job_id__icontains=search_query)
        )

    # Counts of the listed jobs, before the search
    by_status = dict(listed.order_by().values_list('status').annotate(n=Count('id')))
    stats = {
        'total_jobs': sum(by_status.values()),
        'running_jobs': by_status.get('running', 0),
        'awaiting_input_jobs': by_status.get('awaiting_input', 0),
        'pending_jobs': by_status.get('pending', 0),
        'idle_jobs': by_status.get('idle', 0),
        'completed_jobs': by_status.get('completed', 0),
        'failed_jobs': by_status.get('failed', 0),
    }

    # Get list of running job IDs for AJAX updates
    running_job_ids = json.dumps(list(jobs.filter(status__in=LIVE_STATUSES).values_list('id', flat=True)))

    context = {
        'jobs': jobs,
        'config': config,
        'stats': stats,
        'running_job_ids': running_job_ids,
        'page_title': 'RMG Importer Dashboard',
        'search_query': search_query,
    }

    return render(request, 'importer_dashboard/index.html', context)


@site_login_required
def job_detail(request, job_id):
    """
    Detailed view of a specific import job
    """
    job = get_object_or_404(ClusterJob, id=job_id)
    config = job.config or ImportJobConfig.objects.filter(is_default=True).first()

    # Get all species with their related data (prefetch for efficiency)
    species_list = job.species.prefetch_related(
        'votes',
        'votes__candidate',
        'vote_candidates',
        'vote_candidates__voting_reactions',
        'thermo_matches',
        'thermo_matches__candidate',
        'candidates',
    ).select_related(
        'chemkin_thermo',
        'identified_by',
    ).all()

    # Get other related data
    species_identifications = job.species_identifications.select_related('identified_by').all()
    identified_species_list = job.species.filter(
        identification_status='confirmed'
    ).select_related('identified_by').order_by('-confirmed_at', 'chemkin_label')
    blocked_matches = job.blocked_matches.select_related('blocked_by').all()

    # Calculate summary statistics
    stats = {
        'total_species': species_list.count(),
        'identified_species': species_list.filter(identification_status='confirmed').count(),
        'processed_species': species_list.filter(identification_status='processed').count(),
        'unidentified_species': species_list.filter(identification_status='unidentified').count(),
        'total_votes': VotingReaction.objects.filter(candidate__species__job=job).count(),
        'total_candidates': sum(s.candidates.count() for s in species_list),
        'blocked_matches': blocked_matches.count(),
    }
    
    dashboard_logger.info(
        f"Viewing job details", 
        "dashboard",
        job_id=job.id,
        job_name=job.name,
        details={
            'status': job.status,
            'host': job.host or 'Not assigned',
            'port': job.port,
            'tunnel_active': job.tunnel_active
        }
    )
    
    # Check if host needs to be updated
    if job.status == 'running' and (not job.host or job.host == 'Pending...') and config:
        try:
            dashboard_logger.info(
                "Refreshing job status", 
                "dashboard",
                job_id=job.id,
                job_name=job.name
            )
            manager = get_job_manager(config=config)
            manager.refresh_statuses()
            job.refresh_from_db()
            dashboard_logger.success(
                f"Updated host: {job.host}", 
                "dashboard",
                job_id=job.id,
                job_name=job.name,
                details={
                    'host': job.host,
                }
            )
        except Exception as e:
            dashboard_logger.warning(
                f"Could not refresh job status: {str(e)}", 
                "dashboard",
                job_id=job.id,
                job_name=job.name,
                details={
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
    
    # Now try to fetch live progress if we have a valid host
    copied_proposals = None  # copied-chemistry proposals waiting on the importer's copied.html page
    if job.status in LIVE_STATUSES and job.host and job.host != 'Pending...' and config:
        try:
            manager = get_job_manager(config=config) if 'manager' not in locals() else manager

            dashboard_logger.info(
                "Attempting to fetch live progress", 
                "dashboard",
                job_id=job.id,
                job_name=job.name,
                details={
                    'host': job.host,
                    'port': job.port,
                }
            )

            progress = manager.get_progress_json(job)
            copied_proposals = (progress or {}).get('copied')
            if apply_progress(job, progress):
                dashboard_logger.success(
                    f"Updated progress: {job.total_species} species, {job.total_reactions} reactions", 
                    "dashboard",
                    job_id=job.id,
                    job_name=job.name,
                    details={
                        'total_species': job.total_species,
                        'processed': job.processed_species,
                        'confirmed': job.confirmed_species,
                        'total_reactions': job.total_reactions
                    }
                )
            else:
                dashboard_logger.warning(
                    "No progress data returned - job may still be initializing", 
                    "dashboard",
                    job_id=job.id,
                    job_name=job.name,
                    details={
                        'suggestion': 'Job may still be starting up.',
                    }
                )
        except Exception as e:
            dashboard_logger.error(
                f"Could not fetch live progress: {str(e)}", 
                "dashboard",
                job_id=job.id,
                job_name=job.name,
                details={
                    'error': str(e),
                    'error_type': type(e).__name__,
                }
            )

    # For completed jobs with no stats, try to fetch from output files
    if job.status == 'completed' and job.total_species == 0 and config:
        try:
            dashboard_logger.info(
                "Fetching completion statistics from output files",
                "dashboard",
                job_id=job.id,
                job_name=job.name
            )
            manager = get_job_manager(config=config) if 'manager' not in locals() else manager
            completion_stats = manager.get_completion_stats(job)

            if apply_progress(job, completion_stats):
                dashboard_logger.success(
                    f"Retrieved completion stats: {job.total_species} species, {job.total_reactions} reactions",
                    "dashboard",
                    job_id=job.id,
                    job_name=job.name,
                    details=completion_stats
                )
        except Exception as e:
            dashboard_logger.warning(
                f"Could not fetch completion stats: {str(e)}",
                "dashboard",
                job_id=job.id,
                job_name=job.name,
                details={
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
    
    # Determine progress status message
    progress_status = None
    if job.status == 'running':
        if not job.host or job.host == 'Pending...':
            progress_status = {
                'type': 'warning',
                'message': 'Job is running but host not yet assigned. Progress will be available once a worker picks up the job.'
            }
        elif job.total_species == 0:
            progress_status = {
                'type': 'warning',
                'message': (
                    f'RMG job is initializing on {job.host}. Live progress will appear once RMG starts processing. '
                    f'If using Open OnDemand, progress is fetched from {job.ood_url or "the configured OOD URL"}.'
                )
            }
    elif job.status == 'awaiting_input':
        progress_status = {
            'type': 'info',
            'message': ('Waiting for someone to confirm a match on the importer page. The importer keeps '
                        'running and keeps its port, but its worker slot is free for other jobs.')
        }
    elif job.status == 'completed':
        if job.total_species > 0:
            progress_status = {
                'type': 'success',
                'message': f'Job completed successfully. Processed {job.total_species} species and {job.total_reactions} reactions.'
            }
        else:
            progress_status = {
                'type': 'warning',
                'message': 'Job completed but no statistics available. Output files may not have been generated.'
            }
    elif job.status == 'failed':
        reason = latest_error(job)
        progress_status = {
            'type': 'danger',
            'message': (f'{reason.splitlines()[0]} See the Error log tab for details.' if reason
                        else 'Job failed. Check the Error Log tab for details.')
        }
    elif job.status == 'pending':
        progress_status = {
            'type': 'info',
            'message': 'Job is pending in the queue. Waiting for an available worker.'
        }
    
    # Get recent logs
    recent_logs = job.logs.all()[:50]
    
    if job.draft_id and job.draft.start_job_after_check and config:
        # A model added on the create page starts once Check files passes
        from .create_model import start_checked_job
        if start_checked_job(job, get_job_manager(config=config)):
            job.refresh_from_db()
    draft = job.draft if job.draft_id and job.draft.is_open else None
    if draft:
        # A merged pull request closes the draft
        draft = github.refresh_pull_request(draft, request.user)
        draft = draft if draft.is_open else None
    draft_changes, draft_error = None, None
    if draft:
        try:
            draft_changes = drafts.changes(draft)
        except drafts.DraftError as e:
            draft_error = str(e)
    last_draft = draft or job.drafts_closed().first()
    pull_request = github.pull_request_action(draft, job, request.user) if draft else None
    github_account = getattr(request.user, 'github_account', None) if request.user.is_authenticated else None

    context = {
        'job': job,
        'draft': draft,
        'last_draft': last_draft,
        'pull_request': pull_request,
        'github_account': github_account,
        'github_configured': github.configured(),
        'draft_changes': draft_changes,
        'draft_check': editor.check_status(draft) if draft else None,
        'draft_error': draft_error,
        'drafts_enabled': drafts.drafts_enabled(),
        'base_branch': drafts.base_branch(),
        'not_a_model': not_a_model(job),
        'recent_logs': recent_logs,
        'page_title': f'Job: {job.name}',
        'progress_status': progress_status,
        'species_list': species_list,
        'species_identifications': species_identifications,
        'identified_species_list': identified_species_list,
        'blocked_matches': blocked_matches,
        'stats': stats,
        'copied_proposals': copied_proposals,
    }
    
    return render(request, 'importer_dashboard/job_detail.html', context)


# --------------------------------------------------------------------------------------
# Removed features
# --------------------------------------------------------------------------------------
#
# The following endpoints existed in earlier iterations of this Django dashboard but are
# not part of the legacy `dashboard_no_tunnel.py` feature set (species identification,
# interactive sessions, log streaming experiments, mechanism coverage, etc.).
#
# We intentionally removed their view functions to keep this app aligned with the legacy
# dashboard and avoid maintaining unused code paths.


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to start import jobs.')
def job_start(request, job_id):
    """
    Start an import job on the cluster
    """
    job = get_object_or_404(ClusterJob, id=job_id)

    # A second importer on the same model would share its files and vote database
    if job.status in (ImportJobStatus.RUNNING, ImportJobStatus.PENDING, ImportJobStatus.AWAITING_INPUT):
        messages.warning(request, f"{job.name} is already {job.get_status_display().lower()}. "
                                  f"Kill it first if you want to start it again.")
        return redirect('importer_dashboard:index')
    if not_a_model(job):
        messages.error(request, f"{job.name} has no import.sh, so it is not a model and there is "
                                f"nothing to import.")
        return redirect('importer_dashboard:job_detail', job_id=job.id)

    dashboard_logger.info(
        f"Starting job: {job.name}", 
        "dashboard",
        job_id=job.id,
        job_name=job.name,
        details={'user': actor_name(request), 'action': 'start'}
    )
    
    config = job.config or ImportJobConfig.objects.filter(is_default=True).first()
    
    if not config:
        dashboard_logger.error(
            "No configuration available", 
            "dashboard",
            job_id=job.id,
            job_name=job.name
        )
        messages.error(request, "No configuration available for this job")
        return redirect('importer_dashboard:index')
    
    try:
        dashboard_logger.info(
            f"Connecting...", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
            details={'action': 'start_job'}
        )
        draft_note = attach_draft(request, job)
        if draft_note is False:
            return redirect('importer_dashboard:job_detail', job_id=job.id)
        manager = get_job_manager(config=config)
        
        dashboard_logger.info(
            f"Submitting job...", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
        )
        # Who started it, before the task runs: the task's commits name this person
        job.started_by = request.user if request.user.is_authenticated else None
        ClusterJob.objects.filter(pk=job.pk).update(started_by=job.started_by)
        task_id, host = manager.start_job(job)

        # Save only these fields: the job object is from before start_job, and a full save
        # could put back a status or counts that the Celery task has already changed
        importer_mode = getattr(settings, 'IMPORTER_MODE', 'cluster')
        if importer_mode == 'local':
            job.celery_task_id = task_id
            ClusterJob.objects.filter(pk=job.pk).update(celery_task_id=task_id)
        else:
            job.slurm_job_id = task_id
            job.mark_as_running(host=host)
            ClusterJob.objects.filter(pk=job.pk).update(slurm_job_id=task_id)
        
        JobLog.objects.create(
            job=job,
            log_type='info',
            message=f'Job started by {actor_name(request)} (ID: {task_id})'
        )
        
        dashboard_logger.success(
            f"Job started successfully", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
            details={
                'task_id': task_id,
                'host': host,
                'user': actor_name(request)
            }
        )
        messages.success(request, f'Job started successfully (ID: {task_id})')
        
    except Exception as e:
        dashboard_logger.error(
            f"Failed to start job: {str(e)}", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
            details={'error': str(e), 'error_type': type(e).__name__}
        )
        logger.error(f"Failed to start job {job.id}: {str(e)}")
        messages.error(request, f'Failed to start job: {str(e)}')
        job.mark_as_failed()
    
    return redirect('importer_dashboard:index')


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to stop import jobs.')
def job_kill(request, job_id):
    """
    Kill a running import job
    """
    job = get_object_or_404(ClusterJob, id=job_id)
    dashboard_logger.info(
        f"Killing job", 
        "dashboard",
        job_id=job.id,
        job_name=job.name,
        details={'slurm_job_id': job.slurm_job_id, 'user': actor_name(request)}
    )
    
    config = job.config or ImportJobConfig.objects.filter(is_default=True).first()
    
    if not job.slurm_job_id and not job.celery_task_id:
        dashboard_logger.warning(
            f"Job has no task ID", 
            "dashboard",
            job_id=job.id,
            job_name=job.name
        )
        messages.error(request, "Job does not have a task ID")
        return redirect('importer_dashboard:index')
    
    try:
        dashboard_logger.info(
            "Cancelling job...", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
            details={'task_id': job.slurm_job_id or job.celery_task_id}
        )
        manager = get_job_manager(config=config)
        
        dashboard_logger.info(
            f"Sending kill command...", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
        )
        manager.kill_job(job)
        
        job.status = ImportJobStatus.CANCELLED
        job.slurm_job_id = None
        job.celery_task_id = None
        job.host = None
        job.completed_at = timezone.now()
        job.save()
        
        JobLog.objects.create(
            job=job,
            log_type='info',
            message=f'Job cancelled by {actor_name(request)}'
        )
        
        dashboard_logger.success(
            f"Job killed successfully", 
            "dashboard",
            job_id=job.id,
            job_name=job.name,
            details={'user': actor_name(request)}
        )
        
        messages.success(request, 'Job cancelled successfully')
        
    except Exception as e:
        dashboard_logger.error(f"❌ Failed to kill job: {str(e)}", "dashboard")
        logger.error(f"Failed to kill job {job.id}: {str(e)}")
        messages.error(request, f'Failed to kill job: {str(e)}')
    
    return redirect('importer_dashboard:index')


def _job_log(job, name):
    """
    The log `name` ('output.log' or 'error.log') of `job` in full (job_logs.read_log), and the
    error message if it could not be read. On a cluster, the job manager reads it over SSH.
    """
    try:
        if jobs_on_this_machine():
            return read_log(job, name), None
        manager = get_job_manager(config=job.config or ImportJobConfig.objects.filter(is_default=True).first())
        text = manager.get_console_output(job) if name == 'output.log' else manager.get_error_log(job)
        return {'name': name, 'exists': text is not None, 'size': len(text or ''), 'modified': None,
                'text': text or '', 'left_out': 0, 'remote': True}, None
    except Exception as e:
        logger.error(f"Could not read {name} of job {job.id}: {e}")
        return None, f'Could not read {name}: {e}'


def _rmg_log(job):
    """RMG-Py-output/RMG.log of `job` for its download link, or None if there is none."""
    if not jobs_on_this_machine():
        return None
    try:
        size = os.path.getsize(log_path(job, 'RMG.log'))
    except OSError:
        return None
    return {'name': 'RMG.log', 'size': size}


@site_login_required
def job_log_view(request, job_id):
    """
    The output log of a job: output.log, all that the importer printed, in full. (RMG.log has only
    what RMG-Py logs, and is empty for some models; it can be downloaded.)
    """
    job = get_object_or_404(ClusterJob, id=job_id)
    log, read_error = _job_log(job, 'output.log')
    # Only this field: a full save would put back a status or counts that changed meanwhile
    ClusterJob.objects.filter(pk=job.pk).update(last_log_update=timezone.now())
    return render(request, 'importer_dashboard/job_log.html', {
        'job': job,
        'log': log,
        'read_error': read_error,
        'rmg_log': _rmg_log(job),
        'page_title': f'Output log: {job.name}',
    })


@site_login_required
def job_error_log_view(request, job_id):
    """The error log of a job: error.log, what the importer wrote to standard error, in full."""
    job = get_object_or_404(ClusterJob, id=job_id)
    log, read_error = _job_log(job, 'error.log')
    error_updated = timezone.now()
    # Only this field: a full save would put back a status or counts that changed meanwhile
    ClusterJob.objects.filter(pk=job.pk).update(last_error_update=error_updated)
    modified = log['modified'] if log else None
    return render(request, 'importer_dashboard/job_error_log.html', {
        'job': job,
        'log': log,
        'read_error': read_error,
        'error_content': log['text'] if log else '',
        'failure_reason': latest_error(job) if job.status == ImportJobStatus.FAILED else None,
        'error_updated': error_updated,
        'error_file_mtime': modified,
        # A running job whose error.log is older than its start: those errors are from a run before
        'error_is_stale': bool(modified and job.started_at and modified < job.started_at),
        'page_title': f'Error log: {job.name}',
    })


@site_login_required
def job_log_download(request, job_id, name):
    """One log of a job (output.log, error.log or RMG.log), the whole file, as a download."""
    job = get_object_or_404(ClusterJob, id=job_id)
    if name not in LOGS or not jobs_on_this_machine():
        raise Http404('No such log')
    try:
        handle = open(log_path(job, name), 'rb')
    except OSError:
        raise Http404(f'{job.name} has no {name}')
    return FileResponse(handle, as_attachment=True, filename=f"{job.name.replace('/', '_')}_{name}",
                        content_type='text/plain; charset=utf-8')


@site_login_required
def refresh_jobs(request):
    """
    Refresh the list of jobs from the cluster
    """
    dashboard_logger.info(
        "Starting job refresh", 
        "dashboard",
        details={
            'user': actor_name(request),
            'action': 'refresh_jobs'
        }
    )
    
    config = ImportJobConfig.objects.filter(is_default=True).first()
    
    if not config:
        dashboard_logger.error(
            "No default configuration found", 
            "dashboard",
            details={
                'user': actor_name(request),
                'error_type': 'ConfigurationError'
            }
        )
        messages.error(request, "No default configuration found")
        return redirect('importer_dashboard:index')
    
    try:
        ssh_username = os.getenv('SSH_USERNAME', 'unknown')
        
        dashboard_logger.info(
            "Connecting to job backend", 
            "dashboard",
            details={
                'user': ssh_username
            }
        )
        manager = get_job_manager(config=config)
        dashboard_logger.success(
            "Connection established", 
            "dashboard",
        )
        
        # Discover possible jobs
        dashboard_logger.info(
            "Discovering jobs", 
            "dashboard",
            details={
                'root_path': config.root_path,
            }
        )
        discovered_jobs = manager.discover_jobs()
        dashboard_logger.success(
            f"Discovered {len(discovered_jobs)} jobs", 
            "dashboard",
            details={
                'jobs_found': len(discovered_jobs),
                'root_path': config.root_path
            }
        )
        
        # Update running jobs status
        dashboard_logger.info(
            "Querying job statuses", 
            "dashboard",
        )
        manager.update_running_jobs_status()
        
        # Get updated counts
        running_count = ClusterJob.objects.filter(status='running').count()
        awaiting_count = ClusterJob.objects.filter(status='awaiting_input').count()
        pending_count = ClusterJob.objects.filter(status='pending').count()
        completed_count = ClusterJob.objects.filter(status='completed').count()

        dashboard_logger.success(
            f"Status updated: {running_count} running, {awaiting_count} awaiting input, "
            f"{pending_count} pending, {completed_count} completed",
            "dashboard",
            details={
                'running': running_count,
                'awaiting_input': awaiting_count,
                'pending': pending_count,
                'completed': completed_count,
                'total_discovered': len(discovered_jobs)
            }
        )
        
        messages.success(request, f'Refreshed {len(discovered_jobs)} jobs from cluster')
        
    except Exception as e:
        dashboard_logger.error(
            f"Failed to refresh jobs: {str(e)}", 
            "dashboard",
            details={
                'error': str(e),
                'error_type': type(e).__name__,
                'user': actor_name(request)
            }
        )
        logger.error(f"Failed to refresh jobs: {str(e)}")
        messages.error(request, f'Failed to refresh jobs: {str(e)}')
    
    return redirect('importer_dashboard:index')


@site_login_required
def refresh_progress(request):
    """
    Refresh progress information for all running jobs
    """
    dashboard_logger.info(
        "Starting progress refresh", 
        "dashboard",
        details={
            'user': actor_name(request),
            'action': 'refresh_progress'
        }
    )
    
    config = ImportJobConfig.objects.filter(is_default=True).first()
    
    if not config:
        dashboard_logger.error(
            "No default configuration found", 
            "dashboard",
            details={
                'user': actor_name(request),
                'error_type': 'ConfigurationError'
            }
        )
        messages.error(request, "No default configuration found")
        return redirect('importer_dashboard:index')
    
    try:
        dashboard_logger.info(
            "Connecting to job backend", 
            "dashboard",
        )
        manager = get_job_manager(config=config)
        dashboard_logger.success(
            "Connection established", 
            "dashboard",
        )
        
        # First update job statuses
        dashboard_logger.info(
            "Updating job statuses", 
            "dashboard",
        )
        manager.update_running_jobs_status()
        
        # Get running jobs with hosts
        running_jobs = ClusterJob.objects.filter(status__in=LIVE_STATUSES).exclude(host=None)
        dashboard_logger.info(
            f"Found {running_jobs.count()} jobs with active hosts", 
            "dashboard",
            details={
                'active_jobs': running_jobs.count(),
                'job_names': [job.name for job in running_jobs[:5]]
            }
        )
        
        # Refresh progress for each job
        updated_count = manager.refresh_all_progress()
        
        dashboard_logger.success(
            f"Progress updated for {updated_count} jobs", 
            "dashboard",
            details={
                'updated_count': updated_count,
                'total_running': running_jobs.count()
            }
        )
        
        # Auto-sync votes for running jobs
        # Note: incremental_sync uses SSH internally; only run in cluster mode
        from .incremental_sync import sync_job_votes_incremental
        synced_jobs = 0
        synced_identified = 0
        synced_votes = 0
        synced_candidates = 0
        
        importer_mode = getattr(settings, 'IMPORTER_MODE', 'cluster')
        
        if importer_mode == 'local':
            # In local mode, vote databases are on the local filesystem.
            # The incremental_sync module expects an SSH manager with exec_command,
            # and our LocalJobManager has that — pass it through.
            dashboard_logger.info(
                "Starting local vote synchronization for running jobs",
                "dashboard",
                details={'job_count': running_jobs.count()}
            )
        else:
            dashboard_logger.info(
                "Starting vote synchronization for running jobs",
                "dashboard",
                details={'job_count': running_jobs.count()}
            )
        
        for job in running_jobs:
            try:
                # Check if we should sync (avoid syncing too frequently)
                last_sync = job.sync_logs.filter(
                    sync_type='incremental',
                    success=True
                ).order_by('-synced_at').first()
                
                # Only sync if it's been more than 5 minutes since last sync
                if last_sync:
                    time_since_sync = (timezone.now() - last_sync.synced_at).total_seconds()
                    if time_since_sync < 300:  # 5 minutes
                        dashboard_logger.info(
                            f"Skipping {job.name} - synced {int(time_since_sync)}s ago",
                            "dashboard"
                        )
                        continue
                
                dashboard_logger.info(f"Syncing votes for {job.name}...", "dashboard")
                
                # Run incremental sync — pass the manager (works for both modes
                # since LocalJobManager implements exec_command)
                result = sync_job_votes_incremental(job, ssh_manager=manager)
                
                if result.get('success'):
                    synced_jobs += 1
                    synced_identified += result.get('identified_synced', 0)
                    synced_votes += result.get('votes_synced', 0)
                    synced_candidates += result.get('votes_synced', 0)
                    
                    # Update job counters from sync results AND actual database counts
                    job.refresh_from_db()
                    job.total_species = result.get('total_species', 0)
                    job.total_reactions = result.get('total_reactions', 0)
                    job.identified_species = job.species.filter(identification_status='confirmed').count()
                    job.processed_species = job.species.count()
                    job.confirmed_species = job.identified_species
                    job.save(update_fields=['total_species', 'total_reactions', 'identified_species',
                                            'processed_species', 'confirmed_species'])
                    
                    dashboard_logger.success(
                        f"Synced votes for {job.name}",
                        "dashboard",
                        details={
                            'job': job.name,
                            'identified': result.get('identified_synced', 0),
                            'candidates': result.get('votes_synced', 0),
                            'total_species': result.get('total_species', 0),
                            'total_reactions': result.get('total_reactions', 0),
                            'message': result.get('message', '')
                        }
                    )
                else:
                    dashboard_logger.warning(
                        f"Sync returned no data for {job.name}: {result.get('message', 'Unknown error')}",
                        "dashboard"
                    )
            except Exception as e:
                dashboard_logger.error(
                    f"Failed to sync votes for {job.name}: {str(e)}",
                    "dashboard",
                    details={'job': job.name, 'error': str(e)}
                )
        
        if synced_jobs > 0:
            messages.success(
                request, 
                f'Refreshed progress for {updated_count} jobs. '
                f'Synced {synced_identified} identified species and {synced_candidates} candidates from {synced_jobs} jobs.'
            )
        else:
            messages.success(request, f'Refreshed progress for {updated_count} jobs')
        
    except Exception as e:
        dashboard_logger.error(
            f"Failed to refresh progress: {str(e)}", 
            "dashboard",
            details={
                'error': str(e),
                'error_type': type(e).__name__,
                'user': actor_name(request)
            }
        )
        logger.error(f"Failed to refresh progress: {str(e)}")
        messages.error(request, f'Failed to refresh progress: {str(e)}')
    
    return redirect('importer_dashboard:index')


def _rmg_models_status(request):
    """The read copy of RMG-models and its last sync with GitHub (read_copy_sync.py), for Settings."""
    from datetime import datetime
    from django.urls import reverse
    from .read_copy_sync import last_status, read_copy_head
    branch, sha = read_copy_head()
    last = last_status()
    if last:
        for key in ('checked_at', 'updated_at'):
            try:
                last[key] = datetime.fromisoformat(last[key]) if last.get(key) else None
            except ValueError:
                last[key] = None
    return {
        'path': drafts.read_copy(),
        'branch': branch,
        'sha': sha,
        'upstream': f'{drafts.remote_name()}/{drafts.base_branch()}',
        'github_repo': github.repository(),
        'last': last,
        'webhook_on': bool(getattr(settings, 'GITHUB_WEBHOOK_SECRET', '')),
        'webhook_url': github.public_url(request, reverse('importer_dashboard:github_webhook')),
    }


@superuser_required('open the Importer settings', 'importer_dashboard:index')
def settings_view(request):
    """
    View and edit the Importer settings (the job configuration). Only a superuser sees them.
    """
    import os
    
    config = ImportJobConfig.objects.filter(is_default=True).first()
    
    if request.method == 'POST':
        # Update all configuration fields
        config.name = request.POST.get('name', config.name)
        config.ssh_host = request.POST.get('ssh_host', config.ssh_host)
        config.ssh_port = int(request.POST.get('ssh_port', config.ssh_port))
        config.root_path = request.POST.get('root_path', config.root_path)
        config.slurm_partition = request.POST.get('slurm_partition', 'west')
        config.slurm_time_limit = request.POST.get('slurm_time_limit', '3-00:00:00')
        config.slurm_memory = request.POST.get('slurm_memory', '32768M')
        config.additional_slurm_args = request.POST.get('additional_slurm_args', '')
        config.conda_env_name = request.POST.get('conda_env_name', config.conda_env_name)
        config.rmg_py_path = request.POST.get('rmg_py_path', config.rmg_py_path)
        config.is_default = request.POST.get('is_default') == 'on'
        config.save()
        
        messages.success(request, 'Settings updated successfully')
        return redirect('importer_dashboard:settings')
    
    context = {
        'config': config,
        'ssh_username': os.environ.get('SSH_USERNAME', 'Not configured'),
        'page_title': 'Dashboard Settings',
        'rmg_models': _rmg_models_status(request),
    }
    
    return render(request, 'importer_dashboard/settings.html', context)


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to reconnect the job backend.')
def reconnect(request):
    """Reconnect / verify the job backend connection"""
    dashboard_logger.info("Verifying backend connection...", "dashboard")
    
    try:
        config = ImportJobConfig.objects.filter(is_default=True).first()
        if config:
            manager = get_job_manager(config=config)
            manager.connect()  # no-op for local, real connect for SSH
            dashboard_logger.success("Backend connection verified", "dashboard")
            messages.success(request, "Backend connection verified successfully")
        else:
            dashboard_logger.error("No default configuration found", "dashboard")
            messages.error(request, "No default configuration found")
    except Exception as e:
        dashboard_logger.error(f"Failed to connect: {str(e)}", "dashboard")
        logger.error(f"Failed to reconnect: {str(e)}")
        messages.error(request, f"Failed to connect: {str(e)}")
    
    return redirect('importer_dashboard:index')


@require_http_methods(["POST"])
@superuser_required('update RMG-models on this server', 'importer_dashboard:index')
def git_pull(request):
    """Update now on the Settings page: fast-forward the read copy to GitHub's master, if safe."""
    from .read_copy_sync import CURRENT, UPDATED, sync
    result = sync('manual')
    if result['status'] in (UPDATED, CURRENT):
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])
    return redirect('importer_dashboard:settings')


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to pause import jobs.')
def job_pause(request, job_id):
    """Pause a running job"""
    try:
        job = get_object_or_404(ClusterJob, id=job_id)
        
        if job.status != 'running':
            messages.error(request, "Job is not running")
            return redirect('importer_dashboard:interactive_session', job_id=job_id)
        
        # Send pause signal (implementation depends on importChemkin.py support)
        job.status = 'paused'
        job.save()
        
        JobLog.objects.create(
            job=job,
            level='info',
            message=f"Job paused by {actor_name(request)}"
        )
        
        messages.success(request, f"Job {job.name} paused")
    except Exception as e:
        logger.error(f"Failed to pause job: {str(e)}")
        messages.error(request, f"Failed to pause job: {str(e)}")
    
    return redirect('importer_dashboard:interactive_session', job_id=job_id)


# --------------------------------------------------------------------------------------
# Log Streaming Views
# --------------------------------------------------------------------------------------

@site_login_required
def stream_logs(request):
    """
    Kept for dashboard pages opened before the log panel switched to polling get_logs.
    It used to stream forever, which held one of gunicorn's few workers per open tab.
    Now it sends the recent messages and ends; the long `retry` makes an old page's
    EventSource reconnect only every 30 seconds.
    """
    events = ['retry: 30000\n\n']
    for msg in dashboard_logger.get_recent_messages(count=20):
        events.append(f"data: {json.dumps(msg)}\n\n")
    response = HttpResponse(''.join(events), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response


@site_login_required
def get_logs(request):
    """
    Polling endpoint for getting recent log messages (fallback for SSE)
    """
    count = int(request.GET.get('count', 20))
    category = request.GET.get('category', None)
    # Only messages newer than this ISO timestamp, so a polling page doesn't repeat any.
    # (Each gunicorn worker keeps its own messages, so ids would differ between polls.)
    after = request.GET.get('after')

    messages = dashboard_logger.get_recent_messages(count=count, category=category)
    if after:
        messages = [m for m in messages if m['timestamp'] > after]
    
    return JsonResponse({
        'messages': messages,
        'count': len(messages)
    })


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to clear the activity log.')
def clear_logs(request):
    """
    Clear all dashboard logs
    """
    dashboard_logger.clear()
    dashboard_logger.info(
        f"Logs cleared by {actor_name(request)}",
        "dashboard",
        details={
            'user': actor_name(request),
            'action': 'clear_logs'
        }
    )
    messages.success(request, "All logs cleared")
    return redirect('importer_dashboard:index')


@site_login_required
def jobs_stats_api(request):
    """
    API endpoint to get current stats for running jobs.
    Used for auto-refresh on the index page.
    
    Returns JSON with stats for all running jobs.
    """
    # Get running jobs, and jobs awaiting input (their progress still changes)
    running_jobs = ClusterJob.objects.filter(status__in=LIVE_STATUSES)
    
    # Optionally filter by specific job IDs
    job_ids = request.GET.get('job_ids', '')
    if job_ids:
        try:
            job_id_list = [int(x) for x in job_ids.split(',') if x.strip()]
            running_jobs = running_jobs.filter(id__in=job_id_list)
        except ValueError:
            pass
    
    # Build response data
    jobs_data = {}
    for job in running_jobs:
        jobs_data[job.id] = {
            'processed': job.processed_species,
            'identified': job.identified_species,
            'total': job.total_species,
            'confirmed': job.confirmed_species,
            'tentative': job.tentative_species,
            'unidentified': job.unidentified_species,
            'status': job.status,
            'host': job.host,
        }
    
    return JsonResponse({
        'jobs': jobs_data,
        'count': len(jobs_data)
    })
