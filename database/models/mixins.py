from django.db import models
from django.contrib.auth.models import User


class NoRevisionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(revision=False)


class RevisionMixin(models.Model):
    APPROVED = "A"
    PENDING = "P"
    DENIED = "D"
    STATUS_CHOICES = (
        (APPROVED, "Approved"),
        (PENDING, "Pending"),
        (DENIED, "Denied"),
    )
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_on = models.DateTimeField(default=None, null=True)
    revision = models.BooleanField(default=False)
    target = models.ForeignKey("self", null=True, on_delete=models.SET_NULL)
    status = models.CharField(choices=STATUS_CHOICES, max_length=1, blank=True)

    objects = NoRevisionManager()

    class Meta:
        abstract = True
