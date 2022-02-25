from dataclasses import dataclass, field
from typing import Set

from .models import Isomer, KineticModel, Kinetics, Reaction, Source, Species, Structure, Thermo, Transport


@dataclass
class Database:
    structures: Set[Structure] = field(default_factory=set)
    isomers: Set[Isomer] = field(default_factory=set)
    species: Set[Species] = field(default_factory=set)
    reactions: Set[Reaction] = field(default_factory=set)
    kinetics: Set[Kinetics] = field(default_factory=set)
    thermo: Set[Thermo] = field(default_factory=set)
    transport: Set[Transport] = field(default_factory=set)
    kinetic_models: Set[KineticModel] = field(default_factory=set)
    sources: Set[Source] = field(default_factory=set)

    def import_kinetic_model(self, kinetic_model: KineticModel) -> None:
        self.kinetic_models.add(kinetic_model)
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
        self.kinetics.add(kinetics)
        self.import_reaction(kinetics.reaction)
        self.import_source(kinetics.source)

    def import_reaction(self, reaction: Reaction) -> None:
        self.reactions.add(reaction)
        for species in [rs.species for rs in reaction.reaction_species]:
            self.import_species(species)

    def import_thermo(self, thermo: Thermo) -> None:
        self.thermo.add(thermo)
        self.import_species(thermo.species)
        self.import_source(thermo.source)

    def import_transport(self, transport: Transport) -> None:
        self.transport.add(transport)
        self.import_species(transport.species)
        self.import_source(transport.source)

    def import_species(self, species: Species) -> None:
        self.species.add(species)
        for isomer in species.isomers:
            self.import_isomer(isomer)

    def import_isomer(self, isomer: Isomer) -> None:
        self.isomers.add(isomer)
        for structure in isomer.structures:
            self.import_structure(structure)

    def import_structure(self, structure: Structure) -> None:
        self.structures.add(structure)

    def import_source(self, source: Source) -> None:
        self.sources.add(source)
