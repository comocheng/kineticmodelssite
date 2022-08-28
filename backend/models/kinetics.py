
from backend.models.model import Model
from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Species


class Arrhenius(Model):
    a: float
    a_si: float
    a_delta: float | None
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: float | None
    e_units: str
    s: str


class ArrheniusEP(Model):
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str


class ColliderSpecies(Model):
    species: Species
    efficiency: float


KineticsData = Arrhenius | ArrheniusEP


class Kinetics(Model):
    reaction: Reaction
    data: KineticsData
    source: Source
    for_reverse: bool
    uncertainty: float | None
    min_temp: float | None
    max_temp: float | None
    min_pressure: float | None
    max_pressure: float | None
    prime_id: str | None = None
