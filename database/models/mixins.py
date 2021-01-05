import uuid

from django.db import models
from django.contrib.auth.models import User


class LatestRevisionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(master=None)


class RevisionManager(models.Manager):
    def approved(self):
        return self.get_queryset().filter(status=self.model.APPROVED)

    def pending(self):
        return self.get_queryset().filter(status=self.model.PENDING)

    def denied(self):
        return self.get_queryset().filter(status=self.model.DENIED)


class ProposalManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=self.model.PENDING)


class RevisionManagerMixin(models.Model):
    objects = RevisionManager()

    class Meta:
        abstract = True


class ProposalManagerMixin(models.Model):
    objects = ProposalManager()

    class Meta:
        abstract = True


class RevisionMixin(models.Model):
    APPROVED = "A"
    PENDING = "P"
    DENIED = "D"
    STATUS_CHOICES = (
        (APPROVED, "Approved"),
        (PENDING, "Pending"),
        (DENIED, "Denied"),
    )
    created_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    created_on = models.DateTimeField(auto_now_add=True)
    original_id = models.UUIDField(default=uuid.uuid4, editable=False)
    proposal_comment = models.TextField(blank=True)
    reviewer_comment = models.TextField(blank=True)
    status = models.CharField(choices=STATUS_CHOICES, max_length=1, blank=True)

    objects = LatestRevisionManager()
    revisions = RevisionManager()

    class Meta:
        abstract = True

    def is_latest(self):
        return hasattr(self, "master")

    def is_approved(self):
        return self.status == self.APPROVED

    def get_revisions(self):
        return self.revisions.filter(original_id=self.original_id)
