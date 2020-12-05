from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from .models import Reaction, Species
from .scripts.import_rmg_models import get_species_hash, get_reaction_hash


@receiver(m2m_changed, sender=Reaction.species.through)
def change_reaction_hash_on_stoichiometry_change(instance):
    instance.hash = get_reaction_hash(instance.stoich_species())
    instance.save()


@receiver(m2m_changed, sender=Species.isomers.through)
def change_species_hash_on_isomers_change(instance):
    instance.hash = get_species_hash(instance.isomers.all())
    instance.save()
