"""
Analysis Signal Handlers

Handles automatic updates when models change or simulations complete.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from database.models import KineticModel
from .models import SimulationRun, SimulationResult, ModelDatasetCoverage, SimulationStatus

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SimulationRun)
def update_coverage_on_run_complete(sender, instance, created, **kwargs):
    """
    Update ModelDatasetCoverage when a SimulationRun completes.
    """
    if instance.status not in [SimulationStatus.COMPLETED, SimulationStatus.FAILED]:
        return
    
    coverage, _ = ModelDatasetCoverage.objects.get_or_create(
        kinetic_model=instance.kinetic_model,
        dataset=instance.dataset
    )
    coverage.update_from_run(instance)
    logger.info(f"Updated coverage for {instance.kinetic_model} × {instance.dataset}")


@receiver(post_save, sender=KineticModel)
def mark_coverage_outdated_on_model_update(sender, instance, created, **kwargs):
    """
    Mark all coverage entries as outdated when a KineticModel is updated.
    """
    if created:
        return  # New models don't have existing coverage
    
    # Mark all coverage for this model as potentially outdated
    updated = ModelDatasetCoverage.objects.filter(
        kinetic_model=instance,
        has_successful_run=True
    ).update(is_outdated=True, needs_rerun=True)
    
    if updated:
        logger.info(f"Marked {updated} coverage entries as outdated for model {instance.model_name}")
