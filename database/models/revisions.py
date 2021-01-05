from database import models
from database.models import mixins


class SpeciesRevision(mixins.RevisionManagerMixin, models.Species):
    class Meta:
        proxy = True


class SpeciesProposal(mixins.ProposalManagerMixin, models.Species):
    class Meta:
        proxy = True


class ReactionRevision(mixins.RevisionManagerMixin, models.Reaction):
    class Meta:
        proxy = True


class ReactionProposal(mixins.ProposalManagerMixin, models.Reaction):
    class Meta:
        proxy = True


class KineticModelRevision(mixins.RevisionManagerMixin, models.KineticModel):
    class Meta:
        proxy = True


class KineticModelProposal(mixins.ProposalManagerMixin, models.KineticModel):
    class Meta:
        proxy = True
