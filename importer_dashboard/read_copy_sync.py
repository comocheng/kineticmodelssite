"""
Keep the read copy of RMG-models (settings.RMG_MODELS_PATH) at GitHub's master.

The downloads, the coverage pages and the evidence index read the read copy, and drafts start from
its <remote>/<base branch>. When a pull request is merged on GitHub, sync() moves the read copy to
the new master, but only by a fast-forward, and only when that is safe:

- the read copy is on the base branch (master);
- no tracked file has a change that nobody committed;
- it has no commits that master does not have;
- no import job is running in it (jobs run in drafts when IMPORTER_WORKSPACES is on).

It never merges, resets or discards anything. When it cannot fast-forward, it says why, and the
next run tries again. The last result is kept in .rmg-models-sync.json next to the read copy, so
the Settings page shows it whichever process ran the sync.

Three things run it: the webhook of the Prometheus GitHub App on a push to master
(draft_views.github_webhook), Celery Beat every 15 minutes in case a delivery is lost
(tasks.sync_rmg_models_read_copy), and Update now on the Settings page (views.git_pull).
"""
import datetime
import fcntl
import json
import logging
import os
from contextlib import contextmanager

from .drafts import DraftError, base_branch, drafts_enabled, git, read_copy, remote_name

logger = logging.getLogger(__name__)

UPDATED, CURRENT, REFUSED, FAILED = 'updated', 'current', 'refused', 'failed'


def _beside_read_copy(name):
    return os.path.join(os.path.dirname(os.path.abspath(read_copy())), name)


def status_path():
    return _beside_read_copy('.rmg-models-sync.json')


def last_status():
    """The result of the last sync (see sync()), or None if none has run."""
    try:
        with open(status_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_status(result):
    path = status_path()
    with open(path + '.tmp', 'w') as f:
        json.dump(result, f, indent=1)
    os.replace(path + '.tmp', path)


def is_git_repository(path):
    return bool(path) and (os.path.isdir(os.path.join(path, '.git')) or os.path.isfile(os.path.join(path, '.git')))


def read_copy_head():
    """(branch or None, commit) of the read copy now, or (None, None) if it is not a git repository."""
    path = read_copy()
    if not is_git_repository(path):
        return None, None
    branch = git(['symbolic-ref', '--quiet', '--short', 'HEAD'], path, check=False).stdout.strip()
    sha = git(['rev-parse', 'HEAD'], path, check=False).stdout.strip()
    return branch or None, sha or None


@contextmanager
def _read_copy_lock():
    """One sync at a time (a file lock, so it holds across the web and Celery processes)."""
    with open(_beside_read_copy('.rmg-models-sync.lock'), 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _jobs_in_read_copy():
    """True if an import job may be writing in the read copy (drafts are off, and a job is live)."""
    if drafts_enabled():
        return False
    from .local_job_manager import ACTIVE_STATUSES
    from .models import ClusterJob
    return ClusterJob.objects.filter(status__in=ACTIVE_STATUSES).exists()


def _short(sha):
    return sha[:8] if sha else '-'


def _plural(count, word):
    return f'{count} {word}{"" if str(count) == "1" else "s"}'


def _fast_forward(path):
    """Fetch and fast-forward the read copy at `path`. Returns (status, message, old, new)."""
    remote, branch = remote_name(), base_branch()
    upstream = f'{remote}/{branch}'
    if _jobs_in_read_copy():
        return REFUSED, 'An import job is running in the read copy; it is updated when no job runs.', None, None
    try:
        git(['fetch', '--quiet', remote, branch], path, timeout=120)
    except DraftError as e:
        return FAILED, f'Could not fetch {upstream}: {e}', None, None

    on = git(['symbolic-ref', '--quiet', '--short', 'HEAD'], path, check=False).stdout.strip()
    old = git(['rev-parse', 'HEAD'], path).stdout.strip()
    new = git(['rev-parse', f'refs/remotes/{upstream}^{{commit}}'], path).stdout.strip()
    if on != branch:
        return (REFUSED, f'The read copy is on {on or "a detached HEAD"}, not {branch}, so it is not '
                         f'updated. Merge that branch into {branch} on GitHub, then check out {branch}.',
                old, new)
    if old == new:
        return CURRENT, f'The read copy is at {upstream} ({_short(new)}).', old, new

    changed = git(['status', '--porcelain', '--untracked-files=no'], path).stdout.splitlines()
    if changed:
        return (REFUSED, f'The read copy has changes that nobody committed in '
                         f'{_plural(len(changed), "tracked file")} (first: {changed[0][3:]}), so it is '
                         f'not updated.', old, new)
    if git(['merge-base', '--is-ancestor', old, new], path, check=False).returncode != 0:
        ahead = git(['rev-list', '--count', f'{new}..{old}'], path).stdout.strip()
        return (REFUSED, f'The read copy has {_plural(ahead, "commit")} that {upstream} does not have, so '
                         f'it is not updated. Open a pull request with them on GitHub.', old, new)

    merged = git(['merge', '--ff-only', '--quiet', upstream], path, check=False)
    if merged.returncode != 0:
        reason = ' '.join((merged.stderr or merged.stdout).strip().splitlines()[:3])
        return REFUSED, f'git could not fast-forward the read copy: {reason}', old, new
    count = git(['rev-list', '--count', f'{old}..{new}'], path).stdout.strip()
    return (UPDATED, f'Moved the read copy from {_short(old)} to {_short(new)}: '
                     f'{_plural(count, "commit")} of {upstream}.', old, new)


def sync(reason='schedule'):
    """
    Bring the read copy to <remote>/<base branch> if that is safe (see the module docstring).
    `reason` says what asked: 'webhook', 'schedule' or 'manual'. Returns, and keeps for the
    Settings page, a dict: status ('updated', 'current', 'refused' or 'failed'), message, old, new,
    reason and checked_at.
    """
    path = read_copy()
    if not is_git_repository(path):
        status, message, old, new = (FAILED, f'The read copy {path or "(RMG_MODELS_PATH)"} is not a git '
                                              f'repository.', None, None)
    else:
        with _read_copy_lock():
            status, message, old, new = _fast_forward(path)

    previous = last_status() or {}
    result = {'status': status, 'message': message, 'old': old, 'new': new, 'reason': reason,
              'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    if status == UPDATED:
        result['updated_at'] = result['checked_at']
    elif previous.get('updated_at'):
        result['updated_at'] = previous['updated_at']
    try:
        _save_status(result)
    except OSError as e:
        logger.warning(f'Could not keep the RMG-models sync result in {status_path()}: {e}')

    if status == UPDATED:
        logger.info(message)
        from .tasks import schedule_evidence_index_refresh
        schedule_evidence_index_refresh()
    elif status == CURRENT or (previous.get('status'), previous.get('message')) == (status, message):
        logger.debug(message)  # every 15 minutes: say a refusal once, not each time
    else:
        logger.warning(message)
    return result
