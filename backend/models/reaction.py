from dataclasses import field
from uuid import UUID, uuid4

from pydantic import confrozenset
from pydantic.dataclasses import dataclass
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
    prime_id: str
    reaction_species: confrozenset(ReactionSpecies, min_items=0)
    reversible: bool
