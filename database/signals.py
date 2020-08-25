from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Reaction, Stoichiometry


def _flatten_stoich_species(stoich_species):
    return [(stoich, species.id) for stoich, species in stoich_species]


@receiver(post_save, sender=Stoichiometry)
def validate_unique_reaction_stoichiometry(instance, **kwargs):
    reaction = instance.reaction
    stoich_species = _flatten_stoich_species(reaction.stoich_species())
    rest_stoich_species = [
        _flatten_stoich_species(r.stoich_species())
        for r in Reaction.objects.exclude(pk=reaction.pk)
    ]
    if stoich_species in rest_stoich_species:
        raise ValidationError(
            f"stoichiometry-species_id pairs {stoich_species} not unique together in reaction"
        )
