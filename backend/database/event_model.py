from asyncio import Transport
from typing import Iterable
from models.kinetics import Kinetics

from models.species import Isomer, Species, Structure
from models.thermo import Thermo
from models.kinetic_model import KineticModel
from event_store import EventStore

class EventModel:
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def get_kinetic_models(self) -> Iterable[KineticModel]:
        return self._event_store.get_all_kinetic_models()

    def get_species(self) -> Iterable[Species]:
        for km in self.get_kinetic_models():
            for ns in km.named_species:
                yield ns.species

    def get_thermo(self) -> Iterable[Thermo]:
        for km in self.get_kinetic_models():
            yield km.thermo

    def get_transport(self) -> Iterable[Transport]:
        for km in self.get_kinetic_models():
            yield km.transport

    def get_kinetics(self) -> Iterable[Kinetics]:
        for km in self.get_kinetic_models():
            yield km.kinetics

    def get_isomers(self) -> Iterable[Isomer]:
        for species in self.get_species():
            yield from species.isomers

    def get_structures(self) -> Iterable[Structure]:
        for isomer in self.get_isomers():
            yield from isomer.structures
