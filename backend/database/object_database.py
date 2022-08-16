from dataclasses import dataclass, field
from typing import Dict
from uuid import UUID

from backend.database import Database
from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport


@dataclass
class ObjectDatabase(Database):
    structures: Dict[UUID, Structure] = field(default_factory=dict)
    isomers: Dict[UUID, Isomer] = field(default_factory=dict)
    species: Dict[UUID, Species] = field(default_factory=dict)
    reactions: Dict[UUID, Reaction] = field(default_factory=dict)
    kinetics: Dict[UUID, Kinetics] = field(default_factory=dict)
    thermo: Dict[UUID, Thermo] = field(default_factory=dict)
    transport: Dict[UUID, Transport] = field(default_factory=dict)
    kinetic_models: Dict[UUID, KineticModel] = field(default_factory=dict)
    sources: Dict[UUID, Source] = field(default_factory=dict)

    def get_kinetic_model(self, uuid: UUID) -> KineticModel:
        return self.kinetic_models[uuid]

    def get_kinetics(self, uuid: UUID) -> Kinetics:
        return self.kinetics[uuid]

    def get_thermo(self, uuid: UUID) -> Thermo:
        return self.thermo[uuid]

    def get_transport(self, uuid: UUID) -> Transport:
        return self.transport[uuid]

    def get_reaction(self, uuid: UUID) -> Reaction:
        return self.reactions[uuid]

    def get_species(self, uuid: UUID) -> Species:
        return self.species[uuid]

    def get_isomer(self, uuid: UUID) -> Isomer:
        return self.isomers[uuid]

    def get_structure(self, uuid: UUID) -> Structure:
        return self.structures[uuid]

    def import_kinetic_model(self, kinetic_model: KineticModel) -> None:
        self.kinetic_models[kinetic_model.id] = kinetic_model
        self.import_source(kinetic_model.source)
        for species in [ns.species for ns in kinetic_model.named_species]:
            self.import_species(species)
        for kinetics in kinetic_model.kinetics:
            self.import_kinetics(kinetics)
        for thermo in kinetic_model.thermo:
            self.import_thermo(thermo)
        for transport in kinetic_model.transport:
            self.import_transport(transport)

    def import_kinetics(self, kinetics: Kinetics) -> None:
        self.kinetics[kinetics.id] = kinetics
        self.import_reaction(kinetics.reaction)
        self.import_source(kinetics.source)

    def import_reaction(self, reaction: Reaction) -> None:
        self.reactions[reaction.id] = reaction
        for species in [rs.species for rs in reaction.reaction_species]:
            self.import_species(species)

    def import_thermo(self, thermo: Thermo) -> None:
        self.thermo[thermo.id] = thermo
        self.import_species(thermo.species)
        self.import_source(thermo.source)

    def import_transport(self, transport: Transport) -> None:
        self.transport[transport.id] = transport
        self.import_species(transport.species)
        self.import_source(transport.source)

    def import_species(self, species: Species) -> None:
        self.species[species.id] = species
        for isomer in species.isomers:
            self.import_isomer(isomer)

    def import_isomer(self, isomer: Isomer) -> None:
        self.isomers[isomer.id] = isomer
        for structure in isomer.structures:
            self.import_structure(structure)

    def import_structure(self, structure: Structure) -> None:
        self.structures[structure.id] = structure

    def import_source(self, source: Source) -> None:
        self.sources[source.id] = source
