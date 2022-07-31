from typing import FrozenSet

from backend.models.species import Species
from backend.models.utils import Model


class ReactionSpecies(Model):
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


class Reaction(Model):
    prime_id: str
    reaction_species: FrozenSet[ReactionSpecies]
    reversible: bool
