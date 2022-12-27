import pytest

from backend.database.event_store import EventStore
from backend.database.list_event_store import ListEventStore
from backend.models.kinetic_model import KineticModel, NamedSpecies
from backend.models.source import Author, Source
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport


@pytest.fixture
def event_store() -> EventStore:
    return ListEventStore()


@pytest.fixture
def kinetic_model() -> KineticModel:
    structure = Structure(adjlist="", smiles="", multiplicity=0)
    isomer = Isomer(formula="", inchi="", structures=[structure])
    species = Species(isomers=[isomer])
    named_species = NamedSpecies(name="", species=species)
    author = Author(firstname="kian", lastname="mehrabani")
    source = Source(doi="", publication_year=0, title="", journal_name="", journal_volume="", page_numbers="", authors=[author])
    transport = Transport(species=species, geometry=0, well_depth=0, collision_diameter=0, dipole_moment=0, polarizability=0, rotational_relaxation=0, source=source)
    kinetic_model = KineticModel(name="", named_species=[named_species], transport=[transport], source=source)

    return kinetic_model
