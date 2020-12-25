from . import Species, Reaction, Stoichiometry
from .mixins import RevisionManagerMixin


class SpeciesRevision(Species, RevisionManagerMixin):
    pass


class ReactionRevision(Reaction, RevisionManagerMixin):
    pass


class StoichiometryRevision(Stoichiometry, RevisionManagerMixin):
    pass
