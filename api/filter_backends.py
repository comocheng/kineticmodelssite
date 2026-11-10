"""Filter backends that reject query parameters a list endpoint does not support.

The stock backends ignore an unknown parameter or ordering field, so a misspelt
``presure__gte`` or an unsupported ``pressure__gt`` returns the whole table with HTTP 200.
These backends answer HTTP 400 and name the parameters that the endpoint accepts.
"""

# DRF imports this module while it imports rest_framework.viewsets, so rest_flex_fields (which
# imports viewsets) and api.filters (which imports the models) are imported where they are used.
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend, OrderingFilter, SearchFilter
from rest_framework.settings import api_settings


def allowed_query_params(view, queryset):
    """The query parameters that the list action of ``view`` acts on."""
    from rest_flex_fields import EXPAND_PARAM, FIELDS_PARAM, OMIT_PARAM
    from rest_flex_fields.serializers import FlexFieldsSerializerMixin

    allowed = {api_settings.URL_FORMAT_OVERRIDE}
    paginator = getattr(view, "paginator", None)
    if paginator is not None:
        allowed.update(
            name for name in (getattr(paginator, "page_query_param", None),
                              getattr(paginator, "page_size_query_param", None)) if name
        )
    serializer_class = view.get_serializer_class()
    if issubclass(serializer_class, FlexFieldsSerializerMixin):
        allowed.update((EXPAND_PARAM, FIELDS_PARAM, OMIT_PARAM))
    for backend in view.filter_backends:
        if issubclass(backend, DjangoFilterBackend):
            filterset_class = backend().get_filterset_class(view, queryset)
            if filterset_class is not None:
                allowed.update(filterset_class.base_filters)
        elif issubclass(backend, SearchFilter) and getattr(view, "search_fields", None):
            allowed.add(backend.search_param)
        elif issubclass(backend, OrderingFilter):
            allowed.add(backend.ordering_param)
        elif issubclass(backend, RecordKeyFilter) and record_kind_of(view):
            allowed.add(KEY_PARAM)
    return allowed


class StrictDjangoFilterBackend(DjangoFilterBackend):
    """DjangoFilterBackend that answers 400 to a list request with an unknown parameter.

    FilterSets made from a view's ``filterset_fields`` also list a record once, however many
    related rows match (see ``api.filters.FilterSet``).
    """

    @property
    def filterset_base(self):
        from api.filters import FilterSet

        return FilterSet

    def filter_queryset(self, request, queryset, view):
        if getattr(view, "action", None) == "list":
            allowed = allowed_query_params(view, queryset)
            unknown = sorted(set(request.query_params) - allowed)
            if unknown:
                raise ValidationError({
                    "unknown_parameters": unknown,
                    "allowed_parameters": sorted(allowed),
                })
        return super().filter_queryset(request, queryset, view)


class StrictOrderingFilter(OrderingFilter):
    """OrderingFilter that answers 400 to an ordering field the endpoint does not allow."""

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid = super().remove_invalid_fields(queryset, fields, view, request)
        invalid = [term for term in fields if term not in valid]
        if invalid:
            allowed = [item[0] for item in self.get_valid_fields(queryset, view, {"request": request})]
            raise ValidationError({"unknown_ordering": invalid, "allowed_ordering": sorted(allowed)})
        return valid


KEY_PARAM = "key"


def record_kind_of(view):
    """The kind of canonical key (provenance.record_keys) of the records that ``view`` serves."""
    get = getattr(view, "get_serializer_class", None)
    if get is None:
        return None
    try:
        return getattr(get(), "record_kind", None)
    except Exception:
        return None


class RecordKeyFilter(BaseFilterBackend):
    """``?key=`` returns the record with this canonical key (a reaction key without "/f" or "/r"
    gives both directions)."""

    def filter_queryset(self, request, queryset, view):
        value = request.query_params.get(KEY_PARAM)
        kind = record_kind_of(view)
        if not value or not kind:
            return queryset
        from django.contrib.contenttypes.models import ContentType

        from provenance.models import RecordKey

        keys = [value]
        if kind == "reaction" and not value.endswith(("/f", "/r")):
            keys += [f"{value}/f", f"{value}/r"]
        ids = RecordKey.objects.filter(kind=kind, key__in=keys, status=RecordKey.Status.CURRENT,
                                       content_type=ContentType.objects.get_for_model(queryset.model)
                                       ).values("object_id")
        return queryset.filter(pk__in=ids)

    def get_schema_operation_parameters(self, view):
        if not record_kind_of(view):
            return []
        return [{
            "name": KEY_PARAM, "required": False, "in": "query",
            "description": "Canonical key of the record (the end of its canonical URL).",
            "schema": {"type": "string"},
        }]
