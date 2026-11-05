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
    """The model folder of `job`, as a path string. `root` defaults to the read copy."""
    return os.path.join(root or models_root(), job.name)
