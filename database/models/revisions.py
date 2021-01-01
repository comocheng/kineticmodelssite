from . import Species, Reaction, Stoichiometry
from .mixins import RevisionManagerMixin


class SpeciesRevision(RevisionManagerMixin, Species):
    class Meta:
        proxy = True


class ReactionRevision(RevisionManagerMixin, Reaction):
    class Meta:
        proxy = True


class StoichiometryRevision(RevisionManagerMixin, Stoichiometry):
    class Meta:
        proxy = True
