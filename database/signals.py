from django.dispatch import receiver
from django.db.models.signals import m2m_changed, post_save
from .models import Reaction, Species, Structure, ThermoEnrichmentJob, ThermoRecord
from .scripts.import_rmg_models import get_species_hash, get_reaction_hash


@receiver(m2m_changed, sender=Reaction.species.through)
def change_reaction_hash_on_stoichiometry_change(instance, **kwargs):
    instance.hash = get_reaction_hash(instance.stoich_species())
    instance.save()


@receiver(m2m_changed, sender=Species.isomers.through)
def change_species_hash_on_isomers_change(instance, **kwargs):
    instance.hash = get_species_hash(instance.isomers.all())
    instance.save()


@receiver(post_save, sender=Structure)
def enqueue_structure_thermo(sender, instance, created, raw=False, **kwargs):
    # Only database writes here; never call the network or depend on Redis on save.
    if created and not raw:
        ThermoEnrichmentJob.objects.bulk_create([
            ThermoEnrichmentJob(structure=instance, provider=provider)
            for provider in ThermoRecord.SOURCE_PROVIDERS
        ], ignore_conflicts=True)
