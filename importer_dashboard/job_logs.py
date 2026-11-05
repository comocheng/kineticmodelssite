"""
The logs of an import job, read in full from its model folder.

tasks.run_import_job writes two of them: output.log, all that the importer prints, and error.log,
what it writes to standard error. RMG-Py also writes RMG-Py-output/RMG.log, which has only what
RMG-Py logs (for AramcoMech_1.3 it is empty), so the job pages show output.log and error.log.
"""
import datetime
import os

from django.utils import timezone

from .job_paths import job_folder

# Each log a page can show or download, and its path in the model folder
LOGS = {
    'output.log': 'output.log',
    'error.log': 'error.log',
    'RMG.log': os.path.join('RMG-Py-output', 'RMG.log'),
}

# A page shows a log up to this size. Of a larger log it shows the end, where a run stops, and the
# download link gives all of it.
PAGE_BYTES = 5_000_000


def log_path(job, name):
    """The path of the log `name` (a key of LOGS) of `job`."""
    return os.path.join(job_folder(job), LOGS[name])


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
