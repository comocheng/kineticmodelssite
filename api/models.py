from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField


class Revision(models.Model):
    PENDING = "P"
    APPROVED = "A"
    DENIED = "D"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (DENIED, "Denied")]
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="proposals"
    )
    reviewed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="reviews"
    )
    created_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=PENDING)
    proposal_comment = models.TextField(blank=True)
    reviewer_comment = models.TextField(blank=True)
    diff = JSONField(unique=True)

    def __str__(self):
        return f"{self.content_type}\n{self.diff}"

    def is_approved(self):
        return self.status == self.APPROVED
