"""
Pull requests to RMG-models with each person's own GitHub account.

The Prometheus GitHub App (settings GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET) is
installed on the RMG-models repository with the permissions Contents (read and write), Pull
requests (read and write) and Metadata (read). "Connect GitHub" sends a signed-in Prometheus user
through the App's web flow. GitHub returns a user access token: it acts as that person, and only
where both the App and the person have access. It expires after 8 hours and is renewed with the
refresh token (6 months). Both are stored encrypted; they never go into logs, URLs or command
lines (git reads the token through GIT_ASKPASS, from the environment of that one command).

There is no shared token and no push to the base branch: the draft's branch is pushed, and a
pull request into the base branch is opened or updated.
"""

import base64
import hashlib
import logging
import os
import secrets
import stat
from datetime import timedelta
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import drafts
from .models import DraftStatus, GitHubAccount

logger = logging.getLogger(__name__)

API_VERSION = '2022-11-28'
TIMEOUT = 30


class GitHubError(Exception):
    """A GitHub step failed; the message is for the person who asked."""


def configured():
    return bool(
        getattr(settings, 'GITHUB_APP_CLIENT_ID', '')
        and getattr(settings, 'GITHUB_APP_CLIENT_SECRET', '')
    )


def api_url():
    return getattr(settings, 'GITHUB_API_URL', 'https://api.github.com').rstrip('/')


def web_url():
    return getattr(settings, 'GITHUB_WEB_URL', 'https://github.com').rstrip('/')


def repository():
    return getattr(settings, 'RMG_MODELS_GITHUB_REPO', 'comocheng/RMG-models')


def push_url():
    """Where drafts are pushed: the RMG-models repository on GitHub (a setting, for tests)."""
    return getattr(settings, 'RMG_MODELS_PUSH_URL', '') or f'{web_url()}/{repository()}.git'


# ----------------------------------------------------------------------------------------------
# Tokens, encrypted at rest
# ----------------------------------------------------------------------------------------------


def _fernet():
    key = getattr(settings, 'GITHUB_TOKEN_ENCRYPTION_KEY', '')
    if not key:
        # Derived from SECRET_KEY: a new SECRET_KEY means everyone connects GitHub again
        key = base64.urlsafe_b64encode(
            hashlib.sha256(('github-tokens:' + settings.SECRET_KEY).encode()).digest()
        ).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(token):
    return _fernet().encrypt(token.encode()).decode() if token else ''


def decrypt(value):
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as e:
        raise GitHubError(
            'The stored GitHub token cannot be read (the encryption key changed). '
            'Connect GitHub again.'
        ) from e


def _expiry(seconds):
    return timezone.now() + timedelta(seconds=int(seconds)) if seconds else None


# ----------------------------------------------------------------------------------------------
# The web flow
# ----------------------------------------------------------------------------------------------


def public_url(request, path):
    """
    The address of `path` as people and GitHub see it. settings.PUBLIC_SITE_URL (for example
    https://pr.omethe.us) is used when set: behind nginx or Cloudflare, Django can see the request
    as http, and GitHub refuses a callback that is not the https one registered with the App.
    """
    base = getattr(settings, 'PUBLIC_SITE_URL', '').rstrip('/')
    return f'{base}{path}' if base else request.build_absolute_uri(path)


def callback_url(request):
    return public_url(request, '/importer/github/callback/')


def authorize_url(request, state):
    params = {
        'client_id': settings.GITHUB_APP_CLIENT_ID,
        'state': state,
        'redirect_uri': callback_url(request),
        'allow_signup': 'false',
    }
    return f'{web_url()}/login/oauth/authorize?{urlencode(params)}'


def new_state():
    return secrets.token_urlsafe(24)


def _token_request(data):
    try:
        response = requests.post(
            f'{web_url()}/login/oauth/access_token',
            timeout=TIMEOUT,
            headers={'Accept': 'application/json'},
            data={
                'client_id': settings.GITHUB_APP_CLIENT_ID,
                'client_secret': settings.GITHUB_APP_CLIENT_SECRET,
                **data,
            },
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as e:
        raise GitHubError(f'GitHub did not answer: {e}') from e
    if 'access_token' not in payload:
        raise GitHubError(
            "GitHub refused: "
            f"{payload.get('error_description') or payload.get('error') or response.status_code}"
        )
    return payload


def _store_tokens(account, payload):
    account.access_token = encrypt(payload['access_token'])
    account.access_token_expires_at = _expiry(payload.get('expires_in'))
    if payload.get('refresh_token'):
        account.refresh_token = encrypt(payload['refresh_token'])
        account.refresh_token_expires_at = _expiry(payload.get('refresh_token_expires_in'))


def connect(user, code, redirect_uri):
    """Exchange the web flow's code for tokens, and link the GitHub account to `user`."""
    payload = _token_request({'code': code, 'redirect_uri': redirect_uri})
    profile = _api('GET', '/user', payload['access_token'])
    existing = GitHubAccount.objects.filter(github_id=profile['id']).exclude(user=user).first()
    if existing:
        raise GitHubError(f"@{profile['login']} is already linked to another Prometheus account.")
    account = GitHubAccount.objects.filter(user=user).first() or GitHubAccount(user=user)
    account.github_id = profile['id']
    account.login = profile['login']
    account.name = profile.get('name') or ''
    _store_tokens(account, payload)
    account.save()
    return account


def disconnect(user):
    """Unlink `user`'s GitHub account, and ask GitHub to revoke the token (best effort)."""
    account = GitHubAccount.objects.filter(user=user).first()
    if not account:
        return
    try:
        token = decrypt(account.access_token)
        requests.delete(
            f'{api_url()}/applications/{settings.GITHUB_APP_CLIENT_ID}/token',
            timeout=TIMEOUT,
            auth=(settings.GITHUB_APP_CLIENT_ID, settings.GITHUB_APP_CLIENT_SECRET),
            headers={'Accept': 'application/vnd.github+json'},
            json={'access_token': token},
        )
    except (GitHubError, requests.RequestException) as e:
        logger.warning(f'Could not revoke the GitHub token of {user.username}: {e}')
    account.delete()


def access_token(account):
    """A valid access token of `account`, renewed with the refresh token when it has expired."""
    soon = timezone.now() + timedelta(minutes=5)
    if account.access_token_expires_at and account.access_token_expires_at < soon:
        if not account.refresh_token or (
            account.refresh_token_expires_at and account.refresh_token_expires_at < timezone.now()
        ):
            raise GitHubError('Your GitHub connection has expired. Connect GitHub again.')
        payload = _token_request(
            {'grant_type': 'refresh_token', 'refresh_token': decrypt(account.refresh_token)}
        )
        _store_tokens(account, payload)
        account.save(
            update_fields=[
                'access_token',
                'access_token_expires_at',
                'refresh_token',
                'refresh_token_expires_at',
                'updated_at',
            ]
        )
    return decrypt(account.access_token)


# ----------------------------------------------------------------------------------------------
# The REST API
# ----------------------------------------------------------------------------------------------


def _api(method, path, token, **kwargs):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': API_VERSION,
    }
    try:
        response = requests.request(
            method, f'{api_url()}{path}', headers=headers, timeout=TIMEOUT, **kwargs
        )
    except requests.RequestException as e:
        raise GitHubError(f'GitHub did not answer: {e}') from e
    if response.status_code >= 400:
        try:
            body = response.json()
            message = body.get('message', '')
            details = '; '.join(
                e.get('message', '') for e in body.get('errors', []) if isinstance(e, dict)
            )
        except ValueError:
            message, details = response.text[:200], ''
        error = GitHubError(
            f'GitHub answered {response.status_code}: {message}{": " + details if details else ""}'
        )
        error.status = response.status_code
        error.details = details
        raise error
    return response.json() if response.content else {}


def can_push(account):
    """True if `account` may push to RMG-models (asked once per 10 minutes)."""
    key = f'importer-github-push:{account.github_id}:{repository()}'
    allowed = cache.get(key)
    if allowed is None:
        try:
            info = _api('GET', f'/repos/{repository()}', access_token(account))
            allowed = bool(info.get('permissions', {}).get('push'))
        except GitHubError as e:
            if getattr(e, 'status', None) in (403, 404):
                allowed = False  # the App is not installed there, or the person has no access
            else:
                raise
        cache.set(key, allowed, 600)
    return allowed


# ----------------------------------------------------------------------------------------------
# Pushing a draft and its pull request
# ----------------------------------------------------------------------------------------------


def _askpass_script():
    """A script that gives git the token from its environment, never from the command line."""
    path = os.path.join(drafts.workspaces_root(), '.git-askpass.sh')
    if not os.path.exists(path):
        os.makedirs(drafts.workspaces_root(), exist_ok=True)
        with open(path, 'w') as f:
            f.write(
                '#!/bin/sh\ncase "$1" in\n  Username*) echo "x-access-token" ;;\n'
                '  *) echo "$PROMETHEUS_GIT_TOKEN" ;;\nesac\n'
            )
        os.chmod(path, stat.S_IRWXU)
    return path


def push(draft, token):
    """Push the draft's branch to RMG-models with `token`. Returns the commit pushed."""
    env = {'GIT_ASKPASS': _askpass_script(), 'PROMETHEUS_GIT_TOKEN': token}
    with drafts.draft_lock(draft):
        head = drafts.git(['rev-parse', 'HEAD'], draft.path).stdout.strip()
        drafts.git(
            [
                '-c',
                'credential.helper=',
                'push',
                '--quiet',
                push_url(),
                f'HEAD:refs/heads/{draft.branch}',
            ],
            draft.path,
            env=env,
            timeout=600,
        )
    return head


def pull_request_text(draft, job, changes, job_url):
    """Title and body of the draft's pull request. No AI attribution."""
    model = draft.model_folder
    title = (
        f'Add {model}'
        if draft.is_new_model
        else f'{model}: identifications from Prometheus import job {job.pk}'
    )
    lines = [
        f'Changes to `{model}` made with the Prometheus Importer.',
        '',
        f'- Import job: [{job.pk}]({job_url}) ({job.get_status_display()}); '
        f'{job.identified_species} of {job.total_species} species identified',
        f'- Branch `{draft.branch}`, from `{draft.base_branch}` {draft.base_sha[:8]}',
        f"- {len(changes['smiles_added'])} SMILES.txt lines added, "
        f"{len(changes['smiles_removed'])} removed",
        '',
    ]
    if changes['smiles_added'] or changes['smiles_removed']:
        lines += [
            'SMILES.txt changes (the person who confirmed each is in its comment):',
            '',
            '```diff',
        ]
        shown = [f'- {line}' for line in changes['smiles_removed']] + [
            f'+ {line}' for line in changes['smiles_added']
        ]
        lines += shown[:300]
        if len(shown) > 300:
            lines.append(f'# ... and {len(shown) - 300} more lines')
        lines += ['```', '']
    if changes['files']:
        lines += (
            ['Files changed:', '']
            + [f"- `{f['status']}` {f['name']}" for f in changes['files'][:100]]
            + ['']
        )
    return title, '\n'.join(lines)


def open_or_update_pull_request(draft, job, user, job_url):
    """
    Commit what is left, push the draft's branch with `user`'s token, and open its pull request
    (or update the open one, which a push does). Returns the draft.
    """
    account = GitHubAccount.objects.filter(user=user).first()
    if account is None:
        raise GitHubError('Connect your GitHub account first.')
    token = access_token(account)
    if not can_push(account):
        raise GitHubError(
            f'@{account.login} cannot push to {repository()}. Ask a maintainer for write access.'
        )
    drafts.checkpoint_job(job, final=True)
    changes = drafts.changes(draft)
    if changes is None or changes['same_as_base']:
        raise GitHubError(f'Nothing to commit: the draft is the same as {draft.base_branch}.')
    if changes['head'] == draft.last_pushed_sha and draft.pr_state == 'open':
        raise GitHubError(f'Already up to date with pull request #{draft.pr_number}.')

    pushed = push(draft, token)
    owner = repository().split('/')[0]
    if draft.pr_number and draft.pr_state == 'open':
        number, url, state = draft.pr_number, draft.pr_url, 'open'  # the push updated it
    else:
        title, body = pull_request_text(draft, job, changes, job_url)
        try:
            pr = _api(
                'POST',
                f'/repos/{repository()}/pulls',
                token,
                json={
                    'title': title,
                    'body': body,
                    'head': draft.branch,
                    'base': draft.base_branch,
                    'maintainer_can_modify': True,
                },
            )
        except GitHubError as e:
            if getattr(e, 'status', None) != 422 or 'already exists' not in getattr(
                e, 'details', ''
            ):
                raise
            found = _api(
                'GET',
                f'/repos/{repository()}/pulls',
                token,
                params={'head': f'{owner}:{draft.branch}', 'state': 'open'},
            )
            if not found:
                raise
            pr = found[0]
        number, url, state = pr['number'], pr['html_url'], pr['state']
    draft.pr_number, draft.pr_url, draft.pr_state = number, url, state
    draft.last_pushed_sha, draft.pushed_by, draft.pushed_at = pushed, user, timezone.now()
    draft.pr_checked_at = timezone.now()
    draft.save(
        update_fields=[
            'pr_number',
            'pr_url',
            'pr_state',
            'last_pushed_sha',
            'pushed_by',
            'pushed_at',
            'pr_checked_at',
            'updated_at',
        ]
    )
    return draft


def refresh_pull_request(draft, user=None, max_age=300):
    """
    Read the state of the draft's pull request (at most every `max_age` seconds), with the token
    of `user` or of the person who pushed. A merged pull request closes the draft.
    """
    if not draft.pr_number or not configured():
        return draft
    if draft.pr_checked_at and (timezone.now() - draft.pr_checked_at).total_seconds() < max_age:
        return draft
    account = None
    for person in (user, draft.pushed_by):
        if person is not None and getattr(person, 'is_authenticated', False):
            account = GitHubAccount.objects.filter(user=person).first()
            if account:
                break
    if account is None:
        return draft
    try:
        pr = _api('GET', f'/repos/{repository()}/pulls/{draft.pr_number}', access_token(account))
    except GitHubError as e:
        logger.warning(f'Could not read pull request #{draft.pr_number}: {e}')
        return draft
    draft.pr_state = 'merged' if pr.get('merged') else pr.get('state', draft.pr_state)
    draft.pr_checked_at = timezone.now()
    draft.save(update_fields=['pr_state', 'pr_checked_at', 'updated_at'])
    if draft.pr_state == 'merged' and draft.is_open:
        drafts.close_draft(draft, DraftStatus.MERGED)
    return draft


def pull_request_action(draft, job, user):
    """
    What the pull-request button of the job page offers: a dict with `kind` ('open', 'update',
    'connect' or None for a disabled button), `label` and `reason` (why it is disabled).
    """

    def disabled(label, reason):
        return {'kind': None, 'label': label, 'reason': reason}

    number = f'#{draft.pr_number}' if draft and draft.pr_number else ''
    if draft is not None and draft.pr_state == 'merged':
        return disabled(f'Merged in {number}', f'Pull request {number} was merged.')
    if not configured():
        return disabled(
            'Open pull request', 'GitHub is not set up on this server (GITHUB_APP_CLIENT_ID).'
        )
    if draft is None:
        return disabled('Open pull request', 'This job has no draft yet.')
    if job.status not in ('completed', 'cancelled'):
        return disabled(
            'Open pull request' if not number else f'Update pull request {number}',
            'Available when the job is Completed or Cancelled.',
        )
    try:
        changes = drafts.changes(draft)
    except drafts.DraftError as e:
        return disabled('Open pull request', f'Could not read the draft: {e}')
    if changes is None or (changes['same_as_base'] and not changes['pending']):
        return disabled('Nothing to commit', f'The draft is the same as {draft.base_branch}.')
    up_to_date = changes['head'] == draft.last_pushed_sha and not changes['pending']
    if draft.pr_state == 'open' and up_to_date:
        return disabled(
            f'Up to date with {number}', f'Pull request {number} has every commit of the draft.'
        )
    if user is None or not user.is_authenticated:
        return disabled(
            'Open pull request', 'Sign in, then connect GitHub, to open a pull request.'
        )
    account = GitHubAccount.objects.filter(user=user).first()
    if account is None:
        return {'kind': 'connect', 'label': 'Connect GitHub to open a pull request', 'reason': ''}
    try:
        allowed = can_push(account)
    except GitHubError as e:
        return disabled('Open pull request', str(e))
    if not allowed:
        return disabled(
            'Open pull request', f'@{account.login} needs write access to {repository()}.'
        )
    if draft.pr_state == 'open':
        return {'kind': 'update', 'label': f'Update pull request {number}', 'reason': ''}
    return {'kind': 'open', 'label': 'Open pull request', 'reason': ''}
