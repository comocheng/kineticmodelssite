"""
Drafts: each model's work in progress is a git branch of RMG-models with its own worktree.

The original Importer ran importChemkin.py inside a git working copy of RMG-models: each
confirmation was appended to the model's SMILES.txt and the libraries were rewritten in place,
and a person then committed and pushed ("SMILES updated on Discovery"). On the office server all
jobs shared one read-only clone, so nothing reached the repository, and deploys (which need a
clean `git status` for `checkout -B`) stopped on, or removed, the identifications.

Now:
- settings.RMG_MODELS_PATH stays the read copy (evidence index, downloads, coverage).
- A job runs in its model's draft: a worktree at RMG_MODELS_WORKSPACES_PATH/<id>-<folder> on
  branch importer/<folder>/<id>, made from <remote>/<base branch> and checked out sparsely (the
  model folder only; RMG-models is about 770 MB checked out, one model folder about 1 MB).
- checkpoint() commits the importer's files to the branch: SMILES.txt and SMILES-BLOCKED.txt
  whenever they change (the importer only appends to them), the RMG libraries only when the
  importer is not writing them (it empties the library folder, then writes it).
- Commits stay on the server until someone opens a pull request (github.py).

Every git command runs without a shell, with a lock per draft, because the Celery task, the
status refresh and web requests can act on the same worktree at once.
"""

import fcntl
import logging
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from glob import glob

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .importer_files import read_importer_state
from .models import Draft, DraftStatus  # noqa: F401 (DraftStatus is used by callers)

logger = logging.getLogger(__name__)

# The files of a model folder that the importer writes and that belong in RMG-models
IDENTIFICATION_FILES = ['SMILES.txt', 'SMILES-BLOCKED.txt']
LIBRARY_FOLDERS = ['RMG-Py-thermo-library', 'RMG-Py-kinetics-library']
# Importer states in which it is not writing its libraries
LIBRARIES_AT_REST = ('awaiting_input', 'finished', 'stopped')
# How often a running job's identifications are committed
CHECKPOINT_SECONDS = 60


class DraftError(Exception):
    """A git step of a draft failed; the message says which, for the person who asked."""


def read_copy():
    return getattr(settings, 'RMG_MODELS_PATH', '')


def workspaces_root():
    return getattr(settings, 'RMG_MODELS_WORKSPACES_PATH', '') or os.path.join(
        os.path.dirname(os.path.abspath(read_copy())), 'RMG-models-drafts'
    )


def remote_name():
    return getattr(settings, 'RMG_MODELS_REMOTE', 'origin')


def base_branch():
    return getattr(settings, 'RMG_MODELS_BASE_BRANCH', 'master')


def drafts_enabled():
    """Jobs run in drafts when IMPORTER_WORKSPACES is on and the read copy is a git repository."""
    if not getattr(settings, 'IMPORTER_WORKSPACES', False):
        return False
    return os.path.isdir(os.path.join(read_copy(), '.git')) or os.path.isfile(
        os.path.join(read_copy(), '.git')
    )


def git(args, cwd, check=True, env=None, timeout=300, input=None):
    """Run git with `args` in `cwd`. Raises DraftError with git's message when check fails."""
    command = ['git', *args]
    full_env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', **(env or {})}
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=full_env,
            timeout=timeout,
            input=input,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DraftError(f"git {args[0]} failed: {e}") from e
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise DraftError(f"git {' '.join(args[:2])} failed: {message}")
    return result


@contextmanager
def draft_lock(draft):
    """Hold the lock of `draft` (a file lock, so it works across the web and Celery processes)."""
    locks = os.path.join(workspaces_root(), '.locks')
    os.makedirs(locks, exist_ok=True)
    with open(os.path.join(locks, f'{draft.pk}.lock'), 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def folder_slug(model_folder):
    """A model folder as a branch name part; PCI2017/038-Labbe-Zhao(30Torr-10Atm) stays as it is."""
    slug = re.sub(r'[^A-Za-z0-9._()/-]+', '-', model_folder)
    slug = re.sub(r'\.{2,}', '.', slug)
    slug = re.sub(r'/+', '/', slug).strip('/.-')
    return re.sub(r'\.lock(?=/|$)', '-lock', slug) or 'model'


def valid_model_folder(model_folder):
    """
    True for a folder name of the RMG-models form: `Name` or `Journal/NNN-Author`, without `..`,
    absolute paths or characters that are hard to use in a shell.
    """
    parts = model_folder.split('/')
    return (
        0 < len(parts) <= 2
        and all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._()+,-]*", p) for p in parts)
        and '..' not in model_folder
    )


def _fetch_base():
    """
    Bring <remote>/<base branch> of the read copy up to date and return (sha, warning). Without
    network access the last fetched commit is used, with a warning.
    """
    remote, branch = remote_name(), base_branch()
    warning = None
    try:
        git(['fetch', '--quiet', remote, branch], read_copy(), timeout=120)
    except DraftError as e:
        warning = (
            f"Could not fetch {remote}/{branch} ({e}); the draft starts from the last "
            f"fetched commit."
        )
        logger.warning(warning)
    ref = f'refs/remotes/{remote}/{branch}'
    result = git(['rev-parse', '--verify', '--quiet', ref + '^{commit}'], read_copy(), check=False)
    if result.returncode != 0:
        raise DraftError(f"The read copy at {read_copy()} has no {remote}/{branch}.")
    return result.stdout.strip(), warning


def model_exists_on_base(model_folder, sha):
    result = git(['cat-file', '-e', f'{sha}:{model_folder}/import.sh'], read_copy(), check=False)
    return result.returncode == 0


def open_draft(model_folder, user=None, is_new_model=False):
    """
    The open draft of `model_folder`, made if there is none. Returns (draft, warning or None).
    A new draft is a branch from <remote>/<base branch> with a sparse worktree of the model
    folder. The vote databases of the folder in the read copy are copied into it, so earlier
    votes and identifications are not lost (the importer offers again those that SMILES.txt
    does not have).
    """
    existing = Draft.objects.filter(model_folder=model_folder, status=DraftStatus.OPEN).first()
    if existing:
        _repair_worktree(existing)
        return existing, None

    if not valid_model_folder(model_folder):
        raise DraftError(f"{model_folder!r} is not a model folder name RMG-models can use.")
    try:
        with transaction.atomic():
            draft = Draft.objects.create(
                model_folder=model_folder,
                created_by=user,
                is_new_model=is_new_model,
                base_branch=base_branch(),
            )
    except IntegrityError:
        # Someone else opened it at the same moment
        return Draft.objects.get(model_folder=model_folder, status=DraftStatus.OPEN), None

    try:
        sha, warning = _fetch_base()
        exists = model_exists_on_base(model_folder, sha)
        if is_new_model and exists:
            raise DraftError(f"{model_folder} is already in RMG-models {draft.base_branch}.")
        if not is_new_model and not exists:
            raise DraftError(f"{model_folder} is not in RMG-models {draft.base_branch}.")
        draft.branch = f"importer/{folder_slug(model_folder)}/{draft.pk}"
        git(['check-ref-format', '--branch', draft.branch], read_copy())
        draft.path = os.path.join(
            workspaces_root(), f"{draft.pk}-{folder_slug(model_folder).replace('/', '__')}"
        )
        draft.base_sha = sha
        os.makedirs(workspaces_root(), exist_ok=True)
        with draft_lock(draft):
            git(
                [
                    'worktree',
                    'add',
                    '--quiet',
                    '--no-checkout',
                    '-b',
                    draft.branch,
                    draft.path,
                    sha,
                ],
                read_copy(),
            )
            git(['sparse-checkout', 'set', '--cone', '--', model_folder], draft.path)
            git(['read-tree', '-mu', 'HEAD'], draft.path)
            _copy_vote_databases(model_folder, draft.path)
        draft.save()
    except Exception:
        _remove_worktree(draft)
        draft.delete()
        raise
    logger.info(f"Opened draft {draft.branch} at {draft.path}")
    return draft, warning


def _copy_vote_databases(model_folder, worktree):
    source = os.path.join(read_copy(), model_folder)
    target = os.path.join(worktree, model_folder)
    for path in glob(os.path.join(source, 'votes_*.db')):
        os.makedirs(target, exist_ok=True)
        shutil.copy2(path, target)


def _repair_worktree(draft):
    """Make the worktree again if it was removed from disk (its branch keeps the commits)."""
    if draft.path and os.path.isdir(draft.path):
        return
    git(['worktree', 'prune'], read_copy(), check=False)
    with draft_lock(draft):
        git(['worktree', 'add', '--quiet', '--no-checkout', draft.path, draft.branch], read_copy())
        git(['sparse-checkout', 'set', '--cone', '--', draft.model_folder], draft.path)
        git(['read-tree', '-mu', 'HEAD'], draft.path)


def _remove_worktree(draft):
    if draft.path and os.path.isdir(draft.path):
        git(['worktree', 'remove', '--force', draft.path], read_copy(), check=False)
        shutil.rmtree(draft.path, ignore_errors=True)
    git(['worktree', 'prune'], read_copy(), check=False)
    if draft.branch:
        git(['branch', '-D', draft.branch], read_copy(), check=False)


def close_draft(draft, status):
    """
    Close a draft as merged or discarded: its worktree and local branch are removed (a merged
    branch is on GitHub). Its jobs run in the read copy again until a new draft is opened.
    """
    with draft_lock(draft):
        # The worktree goes, with the logs and RMG.log of the runs in it: keep them first
        from .job_logs import keep_logs
        for job in draft.jobs.all():
            try:
                keep_logs(job)
            except OSError as e:
                logger.warning(f'Could not keep the logs of {job.name} before closing its draft: {e}')
        _remove_worktree(draft)
    draft.status = status
    draft.save(update_fields=['status', 'updated_at'])
    draft.jobs.update(draft=None)


def model_path(draft):
    return os.path.join(draft.path, draft.model_folder)


def importer_identity():
    return (
        getattr(settings, 'IMPORTER_GIT_NAME', 'Prometheus Importer'),
        getattr(settings, 'IMPORTER_GIT_EMAIL', 'importer@pr.omethe.us'),
    )


def git_identity(user):
    """
    (name, email) for commits made for `user`: their linked GitHub account if any, else their
    name and email in Prometheus, else the Importer's own identity.
    """
    account = getattr(user, 'github_account', None) if user else None
    if account is not None:
        return account.commit_name, account.commit_email
    if user is not None and getattr(user, 'email', ''):
        return (user.get_full_name() or user.username), user.email
    return importer_identity()


def _commit_env(author):
    name, email = importer_identity()
    author_name, author_email = author or (name, email)
    return {
        'GIT_AUTHOR_NAME': author_name,
        'GIT_AUTHOR_EMAIL': author_email,
        'GIT_COMMITTER_NAME': name,
        'GIT_COMMITTER_EMAIL': email,
    }


def _tracked(draft, relpath):
    return (
        git(['ls-files', '--error-unmatch', '--', relpath], draft.path, check=False).returncode == 0
    )


def _numstat(draft, relpath):
    """(added, removed) lines of `relpath` in the staged changes."""
    out = git(['diff', '--cached', '--numstat', '--', relpath], draft.path).stdout.split()
    if len(out) >= 2 and out[0].isdigit():
        return int(out[0]), int(out[1])
    return 0, 0


def checkpoint(draft, include_libraries=False, user=None, job=None):
    """
    Commit the importer's files of `draft` that changed: SMILES.txt and SMILES-BLOCKED.txt, and
    the two libraries if `include_libraries`. Returns the new commit's sha, or None if nothing
    changed.
    """
    if not draft or not draft.is_open or not draft.path or not os.path.isdir(draft.path):
        return None
    folder = draft.model_folder
    names = IDENTIFICATION_FILES + (LIBRARY_FOLDERS if include_libraries else [])
    with draft_lock(draft):
        paths = [
            f'{folder}/{name}'
            for name in names
            if os.path.exists(os.path.join(draft.path, folder, name))
            or _tracked(draft, f'{folder}/{name}')
        ]
        if not paths:
            return None
        git(['add', '-A', '--', *paths], draft.path)
        if git(['diff', '--cached', '--quiet'], draft.path, check=False).returncode == 0:
            return None
        added, removed = _numstat(draft, f'{folder}/SMILES.txt')
        blocked, _ = _numstat(draft, f'{folder}/SMILES-BLOCKED.txt')
        libraries = any(_numstat(draft, f'{folder}/{name}') != (0, 0) for name in LIBRARY_FOLDERS)
        parts = []
        if added:
            parts.append(f"identify {added} species" if added != 1 else "identify 1 species")
        if removed:
            parts.append(f"remove {removed} SMILES.txt line{'s' if removed != 1 else ''}")
        if blocked:
            parts.append(f"block {blocked} match{'es' if blocked != 1 else ''}")
        if libraries:
            parts.append("update the RMG libraries")
        subject = f"{folder}: {', '.join(parts) or 'update the importer files'}"
        body = f"Import job {job.pk} on Prometheus." if job else "Prometheus Importer."
        starter = getattr(job, 'started_by', None) if job else None
        git(
            ['commit', '--quiet', '-m', subject, '-m', body],
            draft.path,
            env=_commit_env(git_identity(user or starter)),
        )
        sha = git(['rev-parse', 'HEAD'], draft.path).stdout.strip()
    Draft.objects.filter(pk=draft.pk).update(
        last_checkpoint_at=timezone.now(), updated_at=timezone.now()
    )
    logger.info(f"Checkpoint of {draft.branch}: {subject} ({sha[:8]})")
    return sha


def checkpoint_job(job, final=False):
    """
    Commit the identifications of a job's draft: at most once a CHECKPOINT_SECONDS while it runs,
    and always at the end (`final`). The libraries go in only when the importer last reported a
    state in which it is not writing them.
    """
    draft = job.draft
    if draft is None or not draft.is_open:
        return None
    if (
        not final
        and draft.last_checkpoint_at
        and (timezone.now() - draft.last_checkpoint_at).total_seconds() < CHECKPOINT_SECONDS
    ):
        return None
    state = read_importer_state(model_path(draft)).get('state')
    try:
        return checkpoint(draft, include_libraries=state in LIBRARIES_AT_REST, job=job)
    except DraftError as e:
        logger.error(f"Could not commit the identifications of {job.name} to {draft.branch}: {e}")
        return None


def changes(draft):
    """
    What the draft changes in RMG-models: commits ahead of its base, changed files, SMILES.txt
    lines added and removed, and files changed but not yet committed.
    """
    if not draft or not draft.path or not os.path.isdir(draft.path):
        return None
    folder = draft.model_folder
    base = draft.base_sha
    head = git(['rev-parse', 'HEAD'], draft.path).stdout.strip()
    commits = []
    for line in git(
        ['log', '--format=%h%x09%an%x09%ad%x09%s', '--date=format:%Y-%m-%d %H:%M', f'{base}..HEAD'],
        draft.path,
    ).stdout.splitlines():
        sha, author, date, subject = (line.split('\t') + ['', '', '', ''])[:4]
        commits.append({'sha': sha, 'author': author, 'date': date, 'subject': subject})
    files = []
    for line in git(
        ['diff', '--name-status', base, 'HEAD', '--', folder], draft.path
    ).stdout.splitlines():
        status, _, name = line.partition('\t')
        files.append(
            {
                'status': status,
                'name': name[len(folder) + 1:] if name.startswith(folder + '/') else name,
            }
        )
    added, removed = [], []
    diff = git(
        ['diff', '--unified=0', base, 'HEAD', '--', f'{folder}/SMILES.txt'], draft.path
    ).stdout
    for line in diff.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            added.append(line[1:])
        elif line.startswith('-') and not line.startswith('---'):
            removed.append(line[1:])
    pending = []
    keep = tuple(f'{folder}/{name}' for name in IDENTIFICATION_FILES + LIBRARY_FOLDERS)
    for line in git(
        ['status', '--porcelain', '--untracked-files=all', '--', *keep], draft.path, check=False
    ).stdout.splitlines():
        name = line[3:]
        pending.append(name[len(folder) + 1:] if name.startswith(folder + '/') else name)
    same_as_base = (
        git(['diff', '--quiet', base, 'HEAD', '--', folder], draft.path, check=False).returncode
        == 0
    )
    return {
        'head': head,
        'commits': commits,
        'files': files,
        'smiles_added': added,
        'smiles_changed': len(added) + len(removed),
        'smiles_removed': removed,
        'pending': pending,
        'same_as_base': same_as_base,
    }
