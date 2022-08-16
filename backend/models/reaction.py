from dataclasses import field
from uuid import UUID, uuid4

from backend.models.species import Species
from pydantic import conlist
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class ReactionSpecies:
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


@dataclass(frozen=True)
class Reaction:
    prime_id: str
    reaction_species: conlist(ReactionSpecies, min_items=0, unique_items=True)
    reversible: bool
    id: UUID = field(default_factory=uuid4, compare=False)
