"""Read-only API for the FAIR provenance/identity layer (``provenance`` app).

Institutions, persons, licenses, external identifiers, and SSSOM semantic
mappings are exposed as read-only endpoints (public read, like the rest of the
metadata layer). They are curated through the admin / management commands, not
written through the API. Follows the platform conventions: FlexFields
serializers with ``?expand=``/``?fields=``/``?omit=`` and ``extend_schema`` tags.
"""

from drf_spectacular.utils import extend_schema
from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny

from provenance import models


class ReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve only. Provenance records are curated, not API-written."""

    permission_classes = [AllowAny]


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
class InstitutionSerializer(FlexFieldsModelSerializer):
    ror_uri = serializers.ReadOnlyField()

    class Meta:
        model = models.Institution
        fields = "__all__"

    expandable_fields = {
        "parent": ("api.provenance_views.InstitutionSerializer", {"read_only": True}),
    }


class PersonSerializer(FlexFieldsModelSerializer):
    name = serializers.ReadOnlyField()
    orcid_uri = serializers.ReadOnlyField()

    class Meta:
        model = models.Person
        fields = "__all__"

    expandable_fields = {
        "affiliation": (InstitutionSerializer, {"read_only": True}),
    }


class LicenseSerializer(FlexFieldsModelSerializer):
    uri = serializers.ReadOnlyField()

    class Meta:
        model = models.License
        fields = "__all__"


class ExternalIdentifierSerializer(FlexFieldsModelSerializer):
    uri = serializers.ReadOnlyField()

    class Meta:
        model = models.ExternalIdentifier
        fields = [
            "id",
            "scheme",
            "value",
            "url",
            "uri",
            "is_primary",
            "content_type",
            "object_id",
        ]


class SemanticMappingSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.SemanticMapping
        fields = "__all__"

    expandable_fields = {
        "species": ("api.views.SpeciesSerializer", {"read_only": True}),
    }


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------
@extend_schema(tags=["provenance"])
class InstitutionViewSet(ReadOnlyViewSet):
    queryset = models.Institution.objects.select_related("parent").all()
    serializer_class = InstitutionSerializer
    filterset_fields = ["country", "parent"]
    search_fields = ["name", "ror_id", "country"]
    ordering_fields = ["name", "id"]


@extend_schema(tags=["provenance"])
class PersonViewSet(ReadOnlyViewSet):
    queryset = models.Person.objects.select_related("affiliation").all()
    serializer_class = PersonSerializer
    filterset_fields = ["affiliation"]
    search_fields = ["family_name", "given_name", "full_name", "orcid"]
    ordering_fields = ["family_name", "id"]


@extend_schema(tags=["provenance"])
class LicenseViewSet(ReadOnlyViewSet):
    queryset = models.License.objects.all()
    serializer_class = LicenseSerializer
    search_fields = ["spdx_id", "name"]
    ordering_fields = ["spdx_id", "id"]


@extend_schema(tags=["provenance"])
class ExternalIdentifierViewSet(ReadOnlyViewSet):
    queryset = models.ExternalIdentifier.objects.select_related("content_type").all()
    serializer_class = ExternalIdentifierSerializer
    filterset_fields = ["scheme", "value", "content_type", "object_id", "is_primary"]
    search_fields = ["value"]
    ordering_fields = ["id"]


@extend_schema(tags=["provenance"])
class SemanticMappingViewSet(ReadOnlyViewSet):
    queryset = models.SemanticMapping.objects.select_related(
        "species", "source", "experiment_dataset", "kinetic_model", "institution", "person"
    ).all()
    serializer_class = SemanticMappingSerializer
    filterset_fields = [
        "subject_id",
        "object_id",
        "predicate_id",
        "mapping_set_id",
        "species",
        "source",
        "experiment_dataset",
        "kinetic_model",
        "institution",
        "person",
    ]
    search_fields = ["subject_id", "subject_label", "object_id", "object_label"]
    ordering_fields = ["subject_id", "confidence", "id"]
