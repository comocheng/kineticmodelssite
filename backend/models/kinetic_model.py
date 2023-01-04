from pydantic import Field, root_validator

from backend.models.kinetics import Kinetics
from backend.models.model import Model
from backend.models.source import Source
from backend.models.species import Species
from backend.models.thermo import Thermo
from backend.models.transport import Transport


class NamedSpecies(Model):
    name: str
    species: Species


class KineticModel(Model):
    name: str
    named_species: list[NamedSpecies] = Field(min_items=1)
    kinetics: list[Kinetics] = []
    thermo: list[Thermo] = []
    transport: list[Transport] = []
    source: Source
    prime_id: str | None = None

    @root_validator
    def check_some_info_present(cls, values):
        assert (
            values["kinetics"] or values["thermo"] or values["transport"]
        ), "Kinetic model must have at least one kinetics, thermo, or transport entry"
        return values
