"""The canonical key and URL of a record in its API response (the ``?key=`` filter is
api.filter_backends.RecordKeyFilter).

A serializer with ``record_kind`` gets two read-only fields, ``key`` and ``canonical_url``
(provenance.record_keys). A list response reads the keys of the whole page in one query.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class RecordKeyFieldsMixin(serializers.Serializer):
    record_kind = None

    key = serializers.SerializerMethodField(help_text="Canonical key of the record; null when it has no identity.")
    canonical_url = serializers.SerializerMethodField(
        help_text="Canonical URL of the record (/id/<kind>/<key>); null when it has no key.")

    def _key_cache(self):
        holder = self.parent if isinstance(self.parent, serializers.ListSerializer) else self
        cache = getattr(holder, "_record_keys", None)
        if cache is None:
            cache = {}
            objects = getattr(holder, "instance", None) if holder is self.parent else None
            if objects is not None:
                from provenance.record_key_sync import keys_for

                ids = [getattr(obj, "pk", None) for obj in objects]
                found = keys_for(self.record_kind, [pk for pk in ids if pk is not None])
                cache.update({pk: found.get(pk) for pk in ids})
            holder._record_keys = cache
        return cache

    @extend_schema_field(OpenApiTypes.STR)
    def get_key(self, obj):
        cache = self._key_cache()
        if obj.pk not in cache:
            from provenance.record_key_sync import keys_for

            cache[obj.pk] = keys_for(self.record_kind, [obj.pk]).get(obj.pk)
        return cache[obj.pk]

    @extend_schema_field(OpenApiTypes.URI)
    def get_canonical_url(self, obj):
        from provenance.record_keys import canonical_url

        key = self.get_key(obj)
        return canonical_url(self.record_kind, key, self.context.get("request")) if key else None
