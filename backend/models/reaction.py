from typing import FrozenSet

from backend.models.species import Species
from backend.models.utils import frozen_dataclass


@frozen_dataclass
class ReactionSpecies:
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


@frozen_dataclass
class Reaction:
    prime_id: str
    reaction_species: FrozenSet[ReactionSpecies]
    reversible: bool
