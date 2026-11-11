from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F
from django.db.models.functions import Upper


class RecordKey(models.Model):
    """The canonical key of a record, from which its canonical URL /id/<kind>/<key> is made.

    A key comes from what identifies the record outside this database (the InChIKey of a
    structure, the species of a reaction, the DOI of a source), so a rebuild of the database
    gives the same key and the same URL. A row is never deleted: when the key of a record
    changes (a corrected identification), the old row says *moved* and names the new key; when
    the record is removed, the row says *retired* and keeps its label (a tombstone).
    """

    class Status(models.TextChoices):
        CURRENT = "current", "current"
        MOVED = "moved", "moved to another key"
        RETIRED = "retired", "record removed"

    kind = models.CharField(max_length=40, db_index=True)
    key = models.CharField(max_length=1000)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    # Not a foreign key: the row stays when the record is deleted.
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CURRENT, db_index=True)
    successor = models.CharField(max_length=1000, blank=True, help_text="The new key of a moved record.")
    label = models.CharField(max_length=500, blank=True, help_text="What the record is, kept after it is removed.")
    reason = models.CharField(max_length=500, blank=True)
    # For a key made from values (kinetics, thermo): the values and the models that gave them, with
    # each model's source commit (provenance.record_keys.snapshots). Kept up to date while the key
    # is current, and kept as it was when the key moves or the record is removed, so that the old
    # canonical URL can still show what it stood for.
    snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "provenance_record_key"
        indexes = [
            models.Index(fields=["kind", "key"]),
            models.Index(fields=["content_type", "object_id", "status"]),
            # The resolver finds a key typed in another letter case (provenance.record_keys.spellings).
            models.Index(F("kind"), Upper("key"), name="provenance_record_key_ikey"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["kind", "key", "content_type", "object_id"],
                                    name="provenance_record_key_unique"),
        ]

    def __str__(self):
        return f"{self.kind}/{self.key} ({self.status})"
