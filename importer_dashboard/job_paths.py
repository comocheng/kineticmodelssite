"""
Where a job's model folder is: the folder the importer runs in, and where the dashboard reads
its logs, progress.json, importer_state.json and vote database.
"""

import os

from django.conf import settings


def models_root():
    """The read copy of RMG-models (settings.RMG_MODELS_PATH)."""
    return getattr(settings, 'RMG_MODELS_PATH', '/path/to/rmg_models')


def job_folder(job, root=None):
    """
    The model folder of `job`, as a path string: in its open draft's worktree if it has one
    (importer_dashboard/drafts.py), else in `root`, which defaults to the read copy.
    """
    draft = getattr(job, 'draft', None)
    if draft is not None and draft.status == 'open' and draft.path:
        return os.path.join(draft.path, draft.model_folder)
    return os.path.join(root or models_root(), job.name)


def jobs_on_this_machine():
    """True when the import jobs run on this server (IMPORTER_MODE 'local'), so their folders are here."""
    return getattr(settings, 'IMPORTER_MODE', 'cluster') == 'local'


def is_model_folder(path):
    """True if `path` is a model folder: a folder with an import.sh, which the importer runs."""
    return os.path.isfile(os.path.join(path, 'import.sh'))


def model_folder_names(root=None):
    """
    The names of the model folders in `root` (default the read copy): a folder with an import.sh
    directly under it (ANL-Brown) or one level down (CombFlame2013/1315-Chang). A journal folder,
    modelComparer or translations has none, so it is not a model. None if `root` is not a folder.
    """
    root = root or models_root()
    if not os.path.isdir(root):
        return None
    names = set()
    for top in os.scandir(root):
        if not top.is_dir() or top.name.startswith('.'):
            continue
        if is_model_folder(top.path):
            names.add(top.name)
        try:
            subfolders = list(os.scandir(top.path))
        except OSError:
            continue
        for sub in subfolders:
            if sub.is_dir() and not sub.name.startswith('.') and is_model_folder(sub.path):
                names.add(f'{top.name}/{sub.name}')
    return names
