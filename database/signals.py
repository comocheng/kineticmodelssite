from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from database import models
from database.scripts.import_rmg_models import get_species_hash, get_reaction_hash


@receiver(m2m_changed, sender=models.Reaction.species.through)
def change_reaction_hash_on_stoichiometry_change(instance, **kwargs):
    instance.hash = get_reaction_hash(instance.stoich_species())
    instance.save()


@receiver(m2m_changed, sender=models.Species.isomers.through)
def change_species_hash_on_isomers_change(instance, **kwargs):
    instance.hash = get_species_hash(instance.isomers.all())
    instance.save()
