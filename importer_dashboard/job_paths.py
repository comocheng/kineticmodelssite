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
