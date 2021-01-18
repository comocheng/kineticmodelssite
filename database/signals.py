from django.dispatch import receiver
from django.db.models.signals import m2m_changed, post_save, post_delete
from .models import Stoichiometry, Species
from .scripts.import_rmg_models import get_species_hash, get_reaction_hash


@receiver([post_save, post_delete], sender=Stoichiometry)
def change_reaction_hash_on_stoichiometry_change(instance, **kwargs):
    reaction = instance.reaction
    reaction.hash = get_reaction_hash(reaction.stoich_species())
    reaction.save()


@receiver(m2m_changed, sender=Species.isomers.through)
def change_species_hash_on_isomers_change(instance, **kwargs):
    instance.hash = get_species_hash(instance.isomers.all())
    instance.save()
