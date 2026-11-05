"""
Views of drafts (importer_dashboard/drafts.py), their pull requests (github.py) and their files
(editor.py): the "Changes in RMG-models" panel of a job page, and its Files tab.
"""

import os

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from kms.access import actor_name, sign_in_redirect, site_login_required, write_login_required

from . import create_model, drafts, editor, github
from .models import ClusterJob, ImportJobStatus, JobLog
from .views import attach_draft


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to discard drafts.')
def draft_discard(request, job_id):
    """Delete the job's draft: its worktree and local branch. A pull request on GitHub stays."""
    job = get_object_or_404(ClusterJob, id=job_id)
    if job.status in (
        ImportJobStatus.RUNNING,
        ImportJobStatus.PENDING,
        ImportJobStatus.AWAITING_INPUT,
    ):
        messages.error(
            request,
            f'{job.name} is {job.get_status_display().lower()}. '
            f'Kill it before you discard its draft.',
        )
        return redirect('importer_dashboard:job_detail', job_id=job.id)
    draft = job.draft
    if draft is None or not draft.is_open:
        messages.info(request, f'{job.name} has no open draft.')
        return redirect('importer_dashboard:job_detail', job_id=job.id)
    branch = draft.branch
    drafts.close_draft(draft, drafts.DraftStatus.DISCARDED)
    JobLog.objects.create(
        job=job, log_type='info', message=f'Draft {branch} discarded by {actor_name(request)}'
    )
    messages.success(request, f'Discarded the draft {branch}.')
    return redirect('importer_dashboard:job_detail', job_id=job.id)


# --------------------------------------------------------------------------------------
# GitHub: pull requests with each person's own account (importer_dashboard/github.py)
# --------------------------------------------------------------------------------------


def _safe_next(request, default='/importer/'):
    from django.utils.http import url_has_allowed_host_and_scheme

    target = request.GET.get('next') or request.session.get('github_next') or default
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return default
    return target


@site_login_required
def github_connect(request):
    """Start the GitHub App's web flow for the signed-in user."""
    if not request.user.is_authenticated:
        return sign_in_redirect(
            request, 'Sign in, then connect GitHub.', next_url=request.get_full_path()
        )
    if not github.configured():
        messages.error(request, 'GitHub is not set up on this server (GITHUB_APP_CLIENT_ID).')
        return redirect(_safe_next(request))
    state = github.new_state()
    request.session['github_state'] = state
    request.session['github_next'] = _safe_next(request)
    return redirect(github.authorize_url(request, state))


@site_login_required
def github_callback(request):
    """GitHub sends the person back here with a code; link their account."""
    target = _safe_next(request)
    if not request.user.is_authenticated:
        return sign_in_redirect(request, 'Sign in, then connect GitHub.', next_url=target)
    expected = request.session.pop('github_state', None)
    if not expected or request.GET.get('state') != expected:
        messages.error(request, 'The GitHub sign-in could not be checked. Try again.')
        return redirect(target)
    if request.GET.get('error'):
        reason = request.GET.get('error_description') or request.GET['error']
        messages.warning(request, f"GitHub: {reason}")
        return redirect(target)
    try:
        account = github.connect(
            request.user,
            request.GET.get('code', ''),
            request.build_absolute_uri('/importer/github/callback/'),
        )
    except github.GitHubError as e:
        messages.error(request, str(e))
        return redirect(target)
    request.session.pop('github_next', None)
    messages.success(request, f'Connected GitHub as @{account.login}.')
    return redirect(target)


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to change your GitHub connection.')
def github_disconnect(request):
    github.disconnect(request.user)
    messages.success(request, 'Disconnected your GitHub account.')
    return redirect(_safe_next(request, request.META.get('HTTP_REFERER', '/importer/')))


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to open pull requests.')
def draft_pull_request(request, job_id):
    """Push the job's draft with the person's GitHub account and open or update its pull request."""
    job = get_object_or_404(ClusterJob, id=job_id)
    draft = job.draft if job.draft_id and job.draft.is_open else None
    action = github.pull_request_action(draft, job, request.user)
    if action['kind'] == 'connect':
        connect = reverse('importer_dashboard:github_connect')
        return redirect(f"{connect}?next={job_detail_path(job)}")
    if action['kind'] not in ('open', 'update'):
        messages.info(request, action['reason'])
        return redirect('importer_dashboard:job_detail', job_id=job.id)
    try:
        github.open_or_update_pull_request(
            draft, job, request.user, request.build_absolute_uri(job_detail_path(job))
        )
    except (github.GitHubError, drafts.DraftError) as e:
        verb = 'update' if action['kind'] == 'update' else 'open'
        messages.error(request, f'Could not {verb} the pull request: {e}')
        return redirect('importer_dashboard:job_detail', job_id=job.id)
    verb = 'Updated' if action['kind'] == 'update' else 'Opened'
    JobLog.objects.create(
        job=job,
        log_type='info',
        message=(
            f'{verb} pull request #{draft.pr_number} ({draft.pr_url}) ' f'by {actor_name(request)}'
        ),
    )
    messages.success(request, f'{verb} pull request #{draft.pr_number}: {draft.pr_url}')
    return redirect('importer_dashboard:job_detail', job_id=job.id)


def job_detail_path(job):
    return reverse('importer_dashboard:job_detail', args=[job.id])


# --------------------------------------------------------------------------------------
# Draft files: edit a model's files on the web (importer_dashboard/editor.py)
# --------------------------------------------------------------------------------------

LIVE_OR_QUEUED = (ImportJobStatus.RUNNING, ImportJobStatus.PENDING, ImportJobStatus.AWAITING_INPUT)


def _editable_draft(request, job):
    """The job's open draft, or None after a message. Files are not changed while the job runs."""
    draft = job.draft if job.draft_id and job.draft.is_open else None
    if draft is None:
        messages.info(
            request, 'Open a draft first: the files are edited in a branch of RMG-models.'
        )
    elif request.method == 'POST' and job.status in LIVE_OR_QUEUED:
        messages.error(
            request,
            f'{job.name} is {job.get_status_display().lower()}: the importer may be '
            'writing its files. Kill it before you change them.',
        )
        return None
    return draft


@site_login_required
@require_http_methods(["POST"])
@write_login_required('Sign in to edit model files.')
def draft_open(request, job_id):
    """Open the draft of the job's model (or use the open one), to edit its files."""
    job = get_object_or_404(ClusterJob, id=job_id)
    if attach_draft(request, job) is None:
        messages.error(request, 'Drafts are off on this server (IMPORTER_WORKSPACES).')
    return redirect('importer_dashboard:draft_files', job_id=job.id)


@site_login_required
def draft_files(request, job_id):
    """The files of the job's draft, with upload and Check files."""
    if not request.user.is_authenticated:
        return sign_in_redirect(
            request, 'Sign in to see and edit model files.', next_url=request.path
        )
    job = get_object_or_404(ClusterJob, id=job_id)
    draft = job.draft if job.draft_id and job.draft.is_open else None

    if request.method == 'POST':
        draft = _editable_draft(request, job)
        if draft is None:
            return redirect('importer_dashboard:draft_files', job_id=job.id)
        if request.POST.get('action') == 'check':
            editor.start_check(draft)
            messages.info(
                request,
                'Checking the files: importChemkin.py --minimal reads them as an import would.',
            )
            return redirect('importer_dashboard:draft_files', job_id=job.id)
        upload = request.FILES.get('file')
        name = (request.POST.get('name') or '').strip() or (upload.name if upload else '')
        try:
            if upload is None:
                raise editor.EditError('Choose a file to upload.')
            if upload.size > editor.MAX_UPLOAD_BYTES:
                raise editor.EditError(
                    f'{upload.name} is larger than {editor.MAX_UPLOAD_BYTES // 2**20} MB.'
                )
            if name in editor.READ_ONLY:
                raise editor.EditError(f'{name} is not changed here.')
            sha = editor.save(
                draft, {name: upload.read()}, request.POST.get('message'), request.user
            )
        except (editor.EditError, drafts.DraftError) as e:
            messages.error(request, str(e))
            return redirect('importer_dashboard:draft_files', job_id=job.id)
        messages.success(
            request, f'Committed {name} ({sha[:8]}).' if sha else f'{name} has not changed.'
        )
        return redirect('importer_dashboard:draft_files', job_id=job.id)

    try:
        file_list = editor.files(draft) if draft else []
    except drafts.DraftError as e:
        file_list = []
        messages.error(request, f'Could not read the draft: {e}')
    context = {
        'job': job,
        'draft': draft,
        'files': file_list,
        'check': editor.check_status(draft) if draft else None,
        'drafts_enabled': drafts.drafts_enabled(),
        'base_branch': drafts.base_branch(),
        'editing_blocked': job.status in LIVE_OR_QUEUED,
        'max_edit_mb': editor.MAX_EDIT_BYTES // 2**20,
        'page_title': f'Files: {job.name}',
    }
    return render(request, 'importer_dashboard/draft_files.html', context)


@site_login_required
def draft_file_edit(request, job_id, name):
    """Edit one text file of the draft: preview the change, then commit it with a message."""
    if not request.user.is_authenticated:
        return sign_in_redirect(request, 'Sign in to edit model files.', next_url=request.path)
    job = get_object_or_404(ClusterJob, id=job_id)
    draft = job.draft if job.draft_id and job.draft.is_open else None
    if draft is None:
        messages.info(
            request, 'Open a draft first: the files are edited in a branch of RMG-models.'
        )
        return redirect('importer_dashboard:draft_files', job_id=job.id)
    try:
        path = editor.safe_name(draft, name)
        if name in editor.READ_ONLY:
            raise editor.EditError(f'{name} is not changed here.')
        if os.path.exists(path) and (
            os.path.getsize(path) > editor.MAX_EDIT_BYTES or editor._binary(path)
        ):
            raise editor.EditError(f'{name} is too large or not text: replace it by upload.')
        current, encoding, newline = editor.read_text(path)
    except editor.EditError as e:
        messages.error(request, str(e))
        return redirect('importer_dashboard:draft_files', job_id=job.id)

    text, preview, errors, warnings = current, None, [], []
    message = ''
    if request.method == 'POST':
        if _editable_draft(request, job) is None:
            return redirect('importer_dashboard:draft_files', job_id=job.id)
        text = request.POST.get('content', '').replace('\r\n', '\n')
        message = request.POST.get('message', '')
        if name == 'SMILES.txt':
            errors, warnings = editor.check_smiles_text(draft, text, current)
        preview = editor.diff(name, current, text)
        if request.POST.get('action') == 'save' and not errors:
            try:
                sha = editor.save(
                    draft,
                    {name: editor.as_file_bytes(text, encoding, newline)},
                    message,
                    request.user,
                )
            except (editor.EditError, drafts.DraftError) as e:
                errors = [str(e)]
            else:
                messages.success(
                    request, f'Committed {name} ({sha[:8]}).' if sha else f'{name} has not changed.'
                )
                return redirect('importer_dashboard:draft_files', job_id=job.id)
    context = {
        'job': job,
        'draft': draft,
        'name': name,
        'text': text,
        'message': message,
        'preview': preview,
        'errors': errors,
        'warnings': warnings,
        'encoding': encoding,
        'newline': 'CRLF' if newline == '\r\n' else 'LF',
        'is_new': not os.path.exists(path),
        'editing_blocked': job.status in LIVE_OR_QUEUED,
        'page_title': f'{name}: {job.name}',
    }
    return render(request, 'importer_dashboard/draft_file_edit.html', context)


# --------------------------------------------------------------------------------------
# Add a model through the Importer (importer_dashboard/create_model.py)
# --------------------------------------------------------------------------------------


@site_login_required
def model_create(request):
    """/kineticmodel/create/: a new model's files go into a draft, and its import job starts."""
    if not request.user.is_authenticated:
        return sign_in_redirect(request, 'Sign in to add a model.', next_url=request.path)
    enabled = drafts.drafts_enabled()
    form = create_model.NewModelForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and enabled and form.is_valid():
        try:
            job, draft, warning = create_model.create(form.cleaned_data, request.user)
        except (drafts.DraftError, editor.EditError) as e:
            form.add_error(None, str(e))
        else:
            if warning:
                messages.warning(request, warning)
            if draft.start_job_after_check:
                messages.success(
                    request,
                    f'Added {draft.model_folder} in draft {draft.branch}. Checking the '
                    'files; the import starts when they pass.',
                )
            else:
                messages.success(request, f'Added {draft.model_folder} in draft {draft.branch}.')
            return redirect('importer_dashboard:job_detail', job_id=job.id)
    context = {
        'form': form,
        'drafts_enabled': enabled,
        'base_branch': drafts.base_branch(),
        'example_import_sh': create_model.import_sh('thermo.txt', 'transport.txt'),
        'folder_files': create_model.FOLDER_FILES,
        'page_title': 'Add a model to the Importer',
    }
    return render(request, 'importer_dashboard/model_create.html', context)
