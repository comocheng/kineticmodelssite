"""
The logs of an import job, read in full.

tasks.run_import_job writes two of them: output.log, all that the importer prints, and error.log,
what it writes to standard error. RMG-Py also writes RMG-Py-output/RMG.log in the model folder,
which has only what RMG-Py logs (for AramcoMech_1.3 it is empty), so the job pages show output.log
and error.log.

The logs are kept in a folder of the job's own, <IMPORTER_LOGS_PATH>/<job id>/, and not in its
model folder: a draft's worktree is deleted when the draft closes, and a checkout or clean-up of
RMG-models can remove files that git does not track. A copy of RMG.log is kept there when a run
ends and when its draft closes. Logs written before this folder existed are read from the model
folder; manage.py collect_job_logs copies them in.
"""
import datetime
import os
import shutil

from django.conf import settings
from django.utils import timezone

from .job_paths import job_folder, models_root

# Each log a page can show or download, and its path in the model folder
LOGS = {
    'output.log': 'output.log',
    'error.log': 'error.log',
    'RMG.log': os.path.join('RMG-Py-output', 'RMG.log'),
}

# A page shows a log up to this size. Of a larger log it shows the end, where a run stops, and the
# download link gives all of it.
PAGE_BYTES = 5_000_000


def logs_root():
    """settings.IMPORTER_LOGS_PATH, by default importer-logs next to the read copy of RMG-models."""
    return getattr(settings, 'IMPORTER_LOGS_PATH', '') or os.path.join(
        os.path.dirname(os.path.abspath(models_root())), 'importer-logs')


def logs_folder(job):
    return os.path.join(logs_root(), str(job.pk))


def kept_path(job, name):
    """Where the log `name` of `job` is kept: in the job's own log folder."""
    return os.path.join(logs_folder(job), name)


def model_folder_path(job, name, root=None):
    """Where the log `name` is in the job's model folder (RMG.log, and logs of older runs)."""
    return os.path.join(job_folder(job, root), LOGS[name])


def log_path(job, name, root=None):
    """
    The file of the log `name` (a key of LOGS) of `job`: the kept one, or, for a log from before the
    log folder existed, the one in the model folder (in `root`, default the read copy). RMG.log is
    the model folder's while it is there (RMG-Py writes it during a run), else the copy kept when
    the run ended. A job that is not saved yet has no log folder.
    """
    there = model_folder_path(job, name, root)
    if getattr(job, 'pk', None) is None:
        return there
    kept = kept_path(job, name)
    if name == 'RMG.log':
        return there if os.path.exists(there) else kept
    return kept if os.path.exists(kept) or not os.path.exists(there) else there


def writing_path(job, name):
    """The kept path of the log `name`, with its folder made, for a run to write to."""
    os.makedirs(logs_folder(job), exist_ok=True)
    return kept_path(job, name)


def keep_logs(job):
    """
    Copy the logs in the job's model folder into its log folder: RMG.log each time (it is the
    latest run's), output.log and error.log of older runs if the log folder has none. Called when a
    run ends and before a draft's worktree is deleted. Returns the names copied.
    """
    copied = []
    for name in LOGS:
        there, kept = model_folder_path(job, name), kept_path(job, name)
        if os.path.isfile(there) and (name == 'RMG.log' or not os.path.exists(kept)):
            shutil.copy2(there, writing_path(job, name))
            copied.append(name)
    return copied


def read_log(job, name, page_bytes=None):
    """
    The log `name` of `job`, as a dict:
    - exists: False if the job has not written it;
    - size, modified: of the file;
    - text: all of the file, or, if it is larger than page_bytes, its last page_bytes from the
      start of a line;
    - left_out, shown: the number of bytes at the start that text leaves out, and in text.
    """
    page_bytes = page_bytes or PAGE_BYTES
    path = log_path(job, name)
    log = {'name': name, 'exists': False, 'size': 0, 'modified': None, 'text': '', 'left_out': 0, 'shown': 0}
    try:
        with open(path, 'rb') as f:
            stat = os.fstat(f.fileno())
            size = stat.st_size
            if size > page_bytes:
                f.seek(size - page_bytes)
                data = f.read(page_bytes)
                line_start = data.find(b'\n') + 1
                if 0 < line_start < len(data):
                    data = data[line_start:]
            else:
                data = f.read()
    except FileNotFoundError:
        return log
    log.update(
        exists=True,
        size=size,
        modified=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone(
            timezone.get_current_timezone()),
        text=data.decode('utf-8', errors='replace'),
        left_out=max(size - len(data), 0),
        shown=len(data),
    )
    return log
