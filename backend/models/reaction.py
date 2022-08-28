from pydantic import Field

from backend.models.model import Model
from backend.models.species import Species


class ReactionSpecies(Model):
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


class Reaction(Model):
    reaction_species: list[ReactionSpecies] = Field(min_items=1)
    reversible: bool
    prime_id: str | None = None
