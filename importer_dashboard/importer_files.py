"""
Files that a running importer (RMG-Py's importChemkin.py) writes in its model folder,
and how the dashboard reads them:

    progress.json        identification counts: total, confirmed, tentative, ...
    importer_state.json  what it is doing: processing, awaiting_input, finished,
                         stopped (its Kill job button) or crashed, plus its pid and port

The names and the exit code below must match importChemkin.py.
"""
import json
import os

PROGRESS_FILE = 'progress.json'
STATE_FILE = 'importer_state.json'

# importChemkin.py exits with this code when stopped with the Kill job button on its page
EXIT_KILLED_FROM_WEB_PAGE = 3


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_progress(job_path):
    """The importer's latest progress counts, or None. Older importers wrote them in RMG-Py-output."""
    for path in (os.path.join(job_path, PROGRESS_FILE),
                 os.path.join(job_path, 'RMG-Py-output', PROGRESS_FILE)):
        progress = _read_json(path)
        if progress:
            return progress
    return None


PROGRESS_FIELDS = [
    'total_species', 'processed_species', 'unprocessed_species', 'confirmed_species',
    'tentative_species', 'unidentified_species', 'identified_species', 'total_reactions',
    'unmatched_reactions', 'matched_reactions', 'thermo_matches_count',
]


def apply_progress(job, progress):
    """
    Copy the importer's progress counts onto the job and save just those fields, so a
    status change made elsewhere in the meantime isn't overwritten. Returns False if
    there were no counts.
    """
    if not progress:
        return False
    job.total_species = progress.get('total', 0)
    job.processed_species = progress.get('processed', 0)
    job.unprocessed_species = progress.get('unprocessed', 0)
    job.confirmed_species = progress.get('confirmed', 0)
    job.tentative_species = progress.get('tentative', 0)
    job.unidentified_species = progress.get('unidentified', 0)
    job.identified_species = progress.get('confirmed', 0) + progress.get('tentative', 0)
    job.total_reactions = progress.get('totalreactions', 0)
    job.unmatched_reactions = progress.get('unmatchedreactions', 0)
    job.matched_reactions = progress.get('totalreactions', 0) - progress.get('unmatchedreactions', 0)
    job.thermo_matches_count = progress.get('thermomatches', 0)
    job.save(update_fields=PROGRESS_FIELDS)
    return True


def read_importer_state(job_path):
    """What the importer last reported doing, as a dict ({} if it never wrote the file)."""
    return _read_json(os.path.join(job_path, STATE_FILE)) or {}


def clear_importer_state(job_path):
    """Remove the state file left by an earlier run, so it isn't mistaken for the new run's."""
    try:
        os.remove(os.path.join(job_path, STATE_FILE))
    except FileNotFoundError:
        pass


def is_process_alive(pid, expect_in_cmdline=None):
    """
    True if `pid` is a running process. A zombie (exited but not yet reaped by its
    parent) counts as not running. Where /proc exists (Linux), also check that the
    process's command line contains `expect_in_cmdline`, so a PID reused by an
    unrelated process isn't mistaken for the importer.
    """
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        pass  # it exists, but belongs to another user
    except OSError:
        return False
    proc = f'/proc/{pid}'
    if not os.path.isdir(proc):
        return True  # no /proc (e.g. macOS): os.kill is all we can check
    try:
        with open(f'{proc}/stat') as f:
            # "pid (command) state ...": the command can contain spaces and brackets
            state = f.read().rsplit(')', 1)[1].split()[0]
        if state == 'Z':
            return False
        if expect_in_cmdline:
            with open(f'{proc}/cmdline', 'rb') as f:
                if expect_in_cmdline.encode() not in f.read():
                    return False
    except (OSError, IndexError):
        return False  # it exited while we were looking
    return True
