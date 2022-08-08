from dataclasses import dataclass, field
import json
from typing import Iterable, Iterator, Type, TypeVar, Generic
from sortedcontainers import SortedSet
from apischema import serialize, deserialize

from backend.database import Database
from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.reaction import Reaction
from backend.models.source import Source
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport
from backend.models.utils import Model

T = TypeVar("T", bound=Model)

@dataclass
class EncodedSet(Generic[T]):
    factory: Type[T]
    encoded: SortedSet[str] = field(default_factory=SortedSet)

    def __post_init__(self, items: Iterable[T] = []):
        for item in items:
            self.add(item)

    def encode(self, value: T) -> str:
        return json.dumps(serialize(value))

    def decode(self, encoded: str) -> T:
        return deserialize(self.factory, json.loads(encoded))

    def add(self, value: T) -> None:
        encoded_value = self.encode(value)
        self.encoded.add(encoded_value)

    def __len__(self) -> int:
        return self.encoded.__len__()

    def __iter__(self) -> Iterator[T]:
        return (self.decode(e) for e in self.encoded.__iter__())

    def __getitem__(self, index: int) -> T:
        encoded_value = self.encoded[index]
        return self.decode(encoded_value)


@dataclass
class ObjectDatabase(Database):
    structures: EncodedSet[Structure] = EncodedSet(factory=Structure)
    isomers: EncodedSet[Isomer] = EncodedSet(factory=Isomer)
    species: EncodedSet[Species] = EncodedSet(factory=Species)
    reactions: EncodedSet[Reaction] = EncodedSet(factory=Reaction)
    kinetics: EncodedSet[Kinetics] = EncodedSet(factory=Kinetics)
    thermo: EncodedSet[Thermo] = EncodedSet(factory=Thermo)
    transport: EncodedSet[Transport] = EncodedSet(factory=Transport)
    kinetic_models: EncodedSet[KineticModel] = EncodedSet(factory=KineticModel)
    sources: EncodedSet[Source] = EncodedSet(factory=Source)

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
