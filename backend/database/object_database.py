from dataclasses import dataclass, field

from sortedcontainers import SortedSet

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
    structures: SortedSet[Structure] = field(default_factory=SortedSet)
    isomers: SortedSet[Isomer] = field(default_factory=SortedSet)
    species: SortedSet[Species] = field(default_factory=SortedSet)
    reactions: SortedSet[Reaction] = field(default_factory=SortedSet)
    kinetics: SortedSet[Kinetics] = field(default_factory=SortedSet)
    thermo: SortedSet[Thermo] = field(default_factory=SortedSet)
    transport: SortedSet[Transport] = field(default_factory=SortedSet)
    kinetic_models: SortedSet[KineticModel] = field(default_factory=SortedSet)
    sources: SortedSet[Source] = field(default_factory=SortedSet)

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
