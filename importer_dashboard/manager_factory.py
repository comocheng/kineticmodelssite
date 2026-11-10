"""
Factory to select the appropriate job manager based on deployment mode.
"""

from django.conf import settings
from .models import ImportJobConfig
def get_job_manager(config: ImportJobConfig = None):
    """
    Return the correct job manager for the current deployment.
    
    Set IMPORTER_MODE = 'local' in settings.py for Celery-based execution.
    Set IMPORTER_MODE = 'cluster' (default) for SSH/SLURM.
    """
    mode = getattr(settings, 'IMPORTER_MODE', 'cluster')

    if config is None:
        config = ImportJobConfig.objects.filter(is_default=True).first()

    if mode == 'local':
        from .local_job_manager import LocalJobManager
        return LocalJobManager(config=config)
    else:
        from .ssh_manager import SSHJobManager
        manager = SSHJobManager(config=config)
        manager.connect()
        return manager