import functools
from django.db import models
from django.contrib.auth.models import User


class NoRevisionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(revision=False)


class RevisionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(revision=True)


class RevisionManagerMixin(models.Model):
    objects = RevisionManager()

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
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_on = models.DateTimeField(default=None, null=True, blank=True)
    revision = models.BooleanField(default=False)
    target = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(choices=STATUS_CHOICES, max_length=1, blank=True)

    objects = NoRevisionManager()

    class Meta:
        abstract = True


def revision_str(func):
    @functools.wraps(func)
    def inner(self):
        if self.revision:
            return (
                f"Revision of {self.target}"
                "| Status: {self.status}"
                "| By: {self.created_by}"
                "| On: {self.created_on}"
            )
        else:
            return func(self)

    return inner
