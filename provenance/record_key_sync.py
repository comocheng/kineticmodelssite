"""Keep the RecordKey rows of one kind equal to the keys that the records have now.

* A record with a new key gets a *current* row.
* A record whose key changed keeps its old row as *moved*, with the new key as successor,
  so that the old canonical URL redirects (HTTP 301).
* A removed record, or a record that has lost its identity, keeps its row as *retired*, with
  its label, so that the old canonical URL gives a tombstone page (HTTP 410). When another
  record has the same key (two records merged into one), the URL resolves to that record.

Rows are never deleted, and a key is never given to another kind of record.
"""
from collections import Counter
from dataclasses import dataclass, field

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from provenance.models import RecordKey
from provenance.record_keys import KINDS, build_keys

BATCH = 2000


@dataclass
class Result:
    kind: str
    records: int = 0
    keyed: int = 0
    created: int = 0
    moved: int = 0
    retired: int = 0
    reactivated: int = 0
    unchanged: int = 0
    shared_keys: int = 0          # keys that more than one current record has
    shared_records: int = 0       # the records with such a key
    examples: list = field(default_factory=list)

    def line(self):
        return (f"{self.kind}: {self.records} records, {self.keyed} with a key; "
                f"new {self.created}, moved {self.moved}, retired {self.retired}, "
                f"back {self.reactivated}, unchanged {self.unchanged}; "
                f"{self.shared_keys} keys shared by {self.shared_records} records")


def assign(kind, apply=False, now=None):
    """Bring the rows of ``kind`` up to date; with apply=False, only count what would change."""
    now = now or timezone.now()
    model = apps.get_model(KINDS[kind].model)
    content_type = ContentType.objects.get_for_model(model)
    result = Result(kind, records=model.objects.count())

    desired = {}
    for object_id, key, label in build_keys(kind):
        desired[object_id] = (key, (label or "")[:500])
    result.keyed = len(desired)
    counts = Counter(key for key, _ in desired.values())
    shared = {key for key, n in counts.items() if n > 1}
    result.shared_keys = len(shared)
    result.shared_records = sum(counts[key] for key in shared)
    result.examples = sorted(shared)[:5]

    rows = list(RecordKey.objects.filter(kind=kind, content_type=content_type))
    current = {row.object_id: row for row in rows if row.status == RecordKey.Status.CURRENT}
    by_identity = {(row.key, row.object_id): row for row in rows}
    existing_ids = set(model.objects.values_list("pk", flat=True))

    create, update = [], []
    for object_id, (key, label) in desired.items():
        row = current.pop(object_id, None)
        if row is not None and row.key == key:
            if row.label != label:
                row.label = label
                update.append(row)
            result.unchanged += 1
            continue
        if row is not None:                       # the identity of the record changed
            row.status, row.successor, row.changed_at = RecordKey.Status.MOVED, key, now
            row.reason = "the identity of the record changed"
            update.append(row)
            result.moved += 1
        old = by_identity.get((key, object_id))
        if old is not None:                       # the record has its earlier key again
            old.status, old.successor, old.label, old.changed_at = RecordKey.Status.CURRENT, "", label, now
            old.reason = ""
            update.append(old)
            result.reactivated += 1
        else:
            create.append(RecordKey(kind=kind, key=key, content_type=content_type, object_id=object_id,
                                    label=label))
            result.created += 1
    for object_id, row in current.items():        # no key now
        row.status, row.changed_at = RecordKey.Status.RETIRED, now
        row.reason = "record removed" if object_id not in existing_ids else "the record has no identity now"
        update.append(row)
        result.retired += 1

    if apply:
        with transaction.atomic():
            RecordKey.objects.bulk_create(create, batch_size=BATCH)
            RecordKey.objects.bulk_update(update, ["status", "successor", "label", "reason", "changed_at"],
                                          batch_size=BATCH)
    return result


def keys_for(kind, object_ids):
    """object id -> current key, for the records of ``kind`` among object_ids."""
    model = apps.get_model(KINDS[kind].model)
    content_type = ContentType.objects.get_for_model(model)
    return dict(RecordKey.objects.filter(kind=kind, content_type=content_type, object_id__in=list(object_ids),
                                         status=RecordKey.Status.CURRENT).values_list("object_id", "key"))
