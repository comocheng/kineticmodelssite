"""
Editing a model's files in its draft on the web: SMILES.txt, source.txt and the CHEMKIN files.

Every save is a commit on the draft's branch, with the person's message. A file keeps its
encoding and line endings (a browser sends CRLF; an LF file stays LF), so a save changes only
the lines that were changed. Check files runs importChemkin.py --minimal on the draft, which
reads the species, thermo, SMILES.txt and reactions with the importer's own rules (formulas,
SMILES.txt spin notation) and stops.
"""

import difflib
import os
import re
import shlex
import signal
import subprocess

from django.conf import settings

from . import drafts
from .importer_files import is_process_alive

# Files the editor shows as text in the browser; larger ones are replaced by upload
MAX_EDIT_BYTES = 5 * 1024 * 1024
# Largest file that can be uploaded
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
# Files of a model folder that are not edited here: what the importer writes, and its output
NOT_EDITABLE_PREFIXES = tuple(drafts.LIBRARY_FOLDERS) + ('RMG-Py-output',)
RUNTIME_NAMES = (
    'progress.json',
    'importer_state.json',
    'output.log',
    'error.log',
    'importChemkin.profile',
    'importChemkin.profile.pdf',
    'thermoHBIcheck.txt',
)
# import.sh is written by Prometheus for new models, and is the RMG-models one for the others
READ_ONLY = ('import.sh',)


class EditError(Exception):
    pass


def _runtime(name):
    base = os.path.basename(name)
    return base in RUNTIME_NAMES or re.fullmatch(r'votes_.*\.db', base) is not None


def import_sh_files(folder):
    """The files that import.sh names, by option: {'species': ..., 'thermo': ..., ...}."""
    path = os.path.join(folder, 'import.sh')
    try:
        text = open(path, encoding='utf-8', errors='replace').read().replace('\\\n', ' ')
    except OSError:
        return {}
    found = {}
    for key in ('species', 'reactions', 'thermo', 'known'):
        match = re.search(rf'--{key}\s+(\S+)', text)
        if match:
            found[key] = match.group(1).strip('"\'')
    return found


def files(draft):
    """The files of the draft's model folder that can be seen or edited here, with their roles."""
    folder = drafts.model_path(draft)
    roles = {}
    for key, name in import_sh_files(folder).items():
        roles.setdefault(name, []).append(
            {
                'species': 'species',
                'reactions': 'mechanism',
                'thermo': 'thermo',
                'known': 'identifications',
            }[key]
        )
    listed = drafts.git(
        ['ls-files', '--cached', '--others', '--exclude-standard', '--', draft.model_folder],
        draft.path,
    ).stdout.splitlines()
    result = []
    for relpath in sorted(set(listed)):
        name = relpath[len(draft.model_folder) + 1:]
        if not name or name.startswith(NOT_EDITABLE_PREFIXES) or _runtime(name):
            continue
        full = os.path.join(folder, name)
        if not os.path.isfile(full):
            continue
        size = os.path.getsize(full)
        lowered = name.lower()
        file_roles = list(roles.get(name, []))
        if name == 'source.txt':
            file_roles.append('source')
        if lowered in ('transport.txt', 'transport.dat', 'tran.dat') or lowered.endswith(
            '_tran.dat'
        ):
            file_roles.append('transport')
        text = size <= MAX_EDIT_BYTES and not _binary(full)
        result.append(
            {
                'name': name,
                'size': size,
                'roles': file_roles,
                'editable': text and name not in READ_ONLY,
                'read_only': name in READ_ONLY,
                'text': text,
            }
        )
    return result


def _binary(path):
    with open(path, 'rb') as f:
        return b'\0' in f.read(8192)


def safe_name(draft, name):
    """The full path of `name` in the draft's model folder, refusing paths that leave it."""
    if not name or name.startswith('/') or '..' in name.split('/') or '\\' in name:
        raise EditError(f'{name!r} is not a file of this model.')
    if name.startswith(NOT_EDITABLE_PREFIXES) or _runtime(name):
        raise EditError(f'{name} is written by the importer; it is not edited here.')
    folder = os.path.realpath(drafts.model_path(draft))
    full = os.path.realpath(os.path.join(folder, name))
    if not full.startswith(folder + os.sep):
        raise EditError(f'{name!r} is not a file of this model.')
    return full


def read_text(path):
    """(text with \\n line ends, encoding, line end) of a file, for the editor."""
    data = open(path, 'rb').read() if os.path.exists(path) else b''
    try:
        text, encoding = data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        text, encoding = data.decode('latin-1'), 'latin-1'
    newline = '\r\n' if text.count('\r\n') > text.count('\n') / 2 and '\r\n' in text else '\n'
    return text.replace('\r\n', '\n'), encoding, newline


def as_file_bytes(text, encoding, newline):
    """The editor's text as the file's bytes: its encoding and its line ends."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if newline != '\n':
        text = text.replace('\n', newline)
    try:
        return text.encode(encoding)
    except UnicodeEncodeError as e:
        raise EditError(
            f'The file is {encoding}, which cannot hold "{text[e.start:e.end]}".'
        ) from e


def diff(name, old, new, limit=3000):
    lines = list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), f'{name} (now)', f'{name} (yours)', lineterm='', n=2
        )
    )
    if len(lines) > limit:
        lines = lines[:limit] + [f'... {len(lines) - limit} more lines']
    return lines


def species_labels(draft):
    """The species names of the mechanism (the SPECIES blocks of import.sh's --species file)."""
    folder = drafts.model_path(draft)
    name = import_sh_files(folder).get('species')
    if not name:
        return None
    try:
        text = open(os.path.join(folder, name), encoding='utf-8', errors='replace').read()
    except OSError:
        return None
    labels = set()
    for block in re.finditer(r'^\s*SPEC(?:IES)?\b(.*?)^\s*END\b', text, re.I | re.M | re.S):
        for line in block.group(1).splitlines():
            labels.update(line.split('!')[0].split())
    return labels


def check_smiles_text(draft, text):
    """
    Quick checks of a SMILES.txt before it is saved: (errors, warnings). Formulas and the spin
    notation are checked by Check files, which uses the importer's own rules.
    """
    errors, warnings = [], []
    labels = species_labels(draft)
    seen = {}
    for number, line in enumerate(text.splitlines(), 1):
        content = line.split('!', 1)[0]
        tokens = content.split()
        if not tokens:
            continue
        if len(tokens) != 2:
            errors.append(
                f'Line {number}: expected a species name and a SMILES, found {len(tokens)} words.'
            )
            continue
        label, smiles = tokens
        if label in seen and seen[label][1] != smiles:
            errors.append(
                f'Line {number}: {label} is already {seen[label][1]} on line {seen[label][0]}.'
            )
        seen.setdefault(label, (number, smiles))
        if labels is not None and label not in labels:
            warnings.append(
                f'Line {number}: {label} is not a species of the mechanism; the importer skips it.'
            )
    return errors, warnings


def save(draft, changes, message, user):
    """
    Write `changes` ({file name: bytes}) in the draft's model folder and commit them with
    `message`. Returns the commit, or None if the files did not change.
    """
    message = (message or '').strip()
    if not message:
        raise EditError('Say what you changed: the message goes into the commit.')
    paths = []
    with drafts.draft_lock(draft):
        for name, data in changes.items():
            full = safe_name(draft, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as f:
                f.write(data)
            paths.append(f'{draft.model_folder}/{name}')
        drafts.git(['add', '--', *paths], draft.path)
        if drafts.git(['diff', '--cached', '--quiet'], draft.path, check=False).returncode == 0:
            return None
        drafts.git(
            [
                'commit',
                '--quiet',
                '-m',
                f'{draft.model_folder}: {message}',
                '-m',
                'Edited on Prometheus.',
            ],
            draft.path,
            env=drafts._commit_env(drafts.git_identity(user)),
        )
        return drafts.git(['rev-parse', 'HEAD'], draft.path).stdout.strip()


# ----------------------------------------------------------------------------------------------
# Check files: importChemkin.py --minimal, in the background
# ----------------------------------------------------------------------------------------------


def _check_dir(draft):
    return os.path.join(drafts.workspaces_root(), '.checks', str(draft.pk))


def start_check(draft):
    """Start importChemkin.py --minimal on the draft's files; the log goes to _check_dir."""
    from .tasks import _build_command_from_import_sh

    folder = drafts.model_path(draft)
    work = _check_dir(draft)
    os.makedirs(work, exist_ok=True)
    for name in ('check.log', 'check.exit'):
        try:
            os.remove(os.path.join(work, name))
        except FileNotFoundError:
            pass
    rmg_py = getattr(settings, 'RMG_PY_PATH', '')
    command = _build_command_from_import_sh(
        os.path.join(folder, 'import.sh'),
        rmg_py,
        getattr(settings, 'CONDA_ENV_NAME', 'rmg_env'),
        folder,
    )
    command += f' --minimal --output-directory {shlex.quote(os.path.join(work, "output"))}'
    log, done = shlex.quote(os.path.join(work, 'check.log')), shlex.quote(
        os.path.join(work, 'check.exit')
    )
    conda_bin = os.path.join(
        getattr(settings, 'CONDA_BASE_PATH', ''),
        'envs',
        getattr(settings, 'CONDA_ENV_NAME', 'rmg_env'),
        'bin',
    )
    env = {
        **os.environ,
        'PYTHONPATH': rmg_py,
        'RMG': rmg_py,
        'PATH': f'{conda_bin}:{os.environ.get("PATH", "")}',
    }
    process = subprocess.Popen(
        f'({command}) > {log} 2>&1; echo $? > {done}',
        shell=True,
        cwd=folder,
        env=env,
        preexec_fn=os.setsid,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(os.path.join(work, 'check.pid'), 'w') as f:
        f.write(str(process.pid))
    return process.pid


def check_status(draft):
    """None (never run), or {'state': running|passed|failed, 'log': last lines}."""
    work = _check_dir(draft)
    if not os.path.exists(os.path.join(work, 'check.pid')):
        return None
    log = ''
    try:
        with open(os.path.join(work, 'check.log'), errors='replace') as f:
            log = ''.join(f.readlines()[-60:])
    except OSError:
        pass
    try:
        code = int(open(os.path.join(work, 'check.exit')).read().strip())
    except (OSError, ValueError):
        pid = int(open(os.path.join(work, 'check.pid')).read().strip() or 0)
        return {'state': 'running' if is_process_alive(pid) else 'failed', 'log': log}
    return {'state': 'passed' if code == 0 else 'failed', 'log': log, 'code': code}


def stop_check(draft):
    try:
        pid = int(open(os.path.join(_check_dir(draft), 'check.pid')).read().strip())
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (OSError, ValueError, ProcessLookupError):
        pass
