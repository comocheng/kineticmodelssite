from typing import List

from pydantic import BaseModel

from .species import Species


class ReactionSpecies(BaseModel):
    """A species and its stoichiometric coefficient

    The coefficient can be positive to represent a product,
    negative to represent a reactant, or zero to represent an inert or spectator species
    """

    coefficient: int
    species: Species


class Reaction(BaseModel):
    prime_id: str
    reaction_species: List[ReactionSpecies]
    reversible: bool
