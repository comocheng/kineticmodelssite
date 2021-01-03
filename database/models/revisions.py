from database import models
from database.models.mixins import RevisionManagerMixin


class SpeciesRevision(RevisionManagerMixin, models.Species):
    class Meta:
        proxy = True


class ReactionRevision(RevisionManagerMixin, models.Reaction):
    class Meta:
        proxy = True


class StoichiometryRevision(RevisionManagerMixin, models.Stoichiometry):
    class Meta:
        proxy = True


class KineticModelRevision(RevisionManagerMixin, models.KineticModel):
    class Meta:
        proxy = True


class SpeciesNameRevision(RevisionManagerMixin, models.SpeciesName):
    class Meta:
        proxy = True


class KineticsCommentRevision(RevisionManagerMixin, models.KineticsComment):
    class Meta:
        proxy = True


class ThermoCommentRevision(RevisionManagerMixin, models.ThermoComment):
    class Meta:
        proxy = True


class TransportCommentRevision(RevisionManagerMixin, models.TransportComment):
    class Meta:
        proxy = True
