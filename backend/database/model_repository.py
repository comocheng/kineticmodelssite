from typing import Iterable
from uuid import UUID
from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport
from backend.database.event_observer import EventObserver


class ModelRepository(EventObserver):
    def __init__(self) -> None:
        self._kinetic_models: dict[UUID, KineticModel] = {}
        self._kinetics: list[Kinetics] = []
        self._thermo: list[Thermo] = []
        self._transport: list[Transport] = []
        self._species: list[Species] = []
        self._isomers: list[Isomer] = []
        self._structures: list[Structure] = []

    def accept(self, kinetic_model: KineticModel) -> None:
        self._kinetic_models[kinetic_model.id] = kinetic_model
        self._kinetics.extend(kinetic_model.kinetics)
        self._thermo.extend(kinetic_model.thermo)
        self._transport.extend(kinetic_model.transport)

        species: list[Species] = [ns.species for ns in kinetic_model.named_species]
        isomers: list[Isomer] = [i for s in species for i in s.isomers]
        structures: list[Structure] = [s for i in isomers for s in i.structures]
        self._species.extend(species)
        self._isomers.extend(isomers)
        self._structures.extend(structures)

    def catch_up(self, kinetic_models: Iterable[KineticModel]) -> None:
        for km in kinetic_models:
            self.accept(km)

    def get_kinetic_model(self, id: UUID) -> KineticModel | None:
        return self._kinetic_models.get(id)

    @property
    def kinetic_models(self) -> list[KineticModel]:
        return list(self._kinetic_models.values())

    @property
    def species(self) -> list[Species]:
        return self._species

    @property
    def thermo(self) -> list[Thermo]:
        return self._thermo

    @property
    def transport(self) -> list[Transport]:
        return self._transport

    @property
    def kinetics(self) -> list[Kinetics]:
        return self._kinetics

    @property
    def isomers(self) -> list[Isomer]:
        return self._isomers

    @property
    def structures(self) -> list[Structure]:
        return self._structures
