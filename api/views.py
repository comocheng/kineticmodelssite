from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, BasePermission, SAFE_METHODS
from rest_framework.response import Response

from database import models
from api import filters, serializers


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class PermissionsViewSet(viewsets.ModelViewSet):
    """Read access is public; create, update, and delete require an admin user."""

    permission_classes = [IsAdminUser | ReadOnly]


@extend_schema(tags=["species"])
class FormulaViewSet(PermissionsViewSet):
    queryset = models.Formula.objects.all()
    serializer_class = serializers.FormulaSerializer
    filterset_fields = ["formula"]
    search_fields = ["formula"]
    ordering_fields = ["id", "formula"]


@extend_schema(tags=["species"])
class IsomerViewSet(PermissionsViewSet):
    queryset = models.Isomer.objects.all()
    serializer_class = serializers.IsomerSerializer
    filterset_fields = ["formula"]
    search_fields = ["inchi"]
    ordering_fields = ["id"]


@extend_schema(tags=["species"])
@extend_schema_view(
    list=extend_schema(summary="List canonical species"),
    retrieve=extend_schema(summary="Retrieve a canonical species by ID"),
)
class SpeciesViewSet(PermissionsViewSet):
    queryset = models.Species.objects.all()
    serializer_class = serializers.SpeciesSerializer
    filterset_fields = ["prime_id", "cas_number", "isomers__formula"]
    search_fields = ["prime_id", "cas_number", "hash", "isomers__inchi"]
    ordering_fields = ["id"]


@extend_schema(tags=["reactions"])
@extend_schema_view(
    list=extend_schema(summary="List reactions"),
    retrieve=extend_schema(summary="Retrieve a reaction (with stoichiometry) by ID"),
)
class ReactionViewSet(PermissionsViewSet):
    queryset = models.Reaction.objects.all()
    serializer_class = serializers.ReactionSerializer
    filterset_fields = ["prime_id", "reversible"]
    search_fields = ["prime_id", "hash"]
    ordering_fields = ["id"]


@extend_schema(tags=["thermo-transport"])
class ThermoViewSet(PermissionsViewSet):
    queryset = models.Thermo.objects.select_related("provider_record").all()
    serializer_class = serializers.ThermoSerializer
    ordering_fields = ["id"]


@extend_schema(tags=["thermo-transport"])
class ThermoRecordViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ReadOnly]
    queryset = models.ThermoRecord.objects.all()
    serializer_class = serializers.ThermoRecordSerializer
    filterset_fields = ["provider", "species", "structure", "source_version", "external_id"]
    ordering_fields = ["id", "retrieved_at"]


@extend_schema(tags=["thermo-transport"])
class ThermoEnrichmentJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ReadOnly]
    queryset = models.ThermoEnrichmentJob.objects.all()
    serializer_class = serializers.ThermoEnrichmentJobSerializer
    filterset_fields = ["provider", "structure", "status"]
    ordering_fields = ["id", "updated_at", "attempts"]


@extend_schema(tags=["thermo-transport"])
class TransportViewSet(PermissionsViewSet):
    queryset = models.Transport.objects.all()
    serializer_class = serializers.TransportSerializer
    ordering_fields = ["id"]


@extend_schema(tags=["reactions"])
class KineticsViewSet(PermissionsViewSet):
    queryset = models.Kinetics.objects.all()
    serializer_class = serializers.KineticsSerializer
    ordering_fields = ["id"]


@extend_schema(tags=["models"])
@extend_schema_view(
    list=extend_schema(summary="List kinetic models"),
    retrieve=extend_schema(summary="Retrieve a kinetic model (with components) by ID"),
)
class KineticModelViewSet(PermissionsViewSet):
    queryset = models.KineticModel.objects.all()
    serializer_class = serializers.KineticModelSerializer
    filterset_class = filters.KineticModelFilter
    search_fields = ["model_name", "prime_id", "info", "source__doi", "source__source_title"]
    ordering_fields = ["id", "model_name"]

    @extend_schema(summary="How many lines of the model's own CHEMKIN file the generated downloads have",
                   responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["get"])
    def coverage(self, request, pk=None):
        """Each reaction line of the model's own CHEMKIN file (the file RMG-models converted) that the
        generated CHEMKIN and Cantera downloads do not have, with the reason; `?lines=all` gives every
        line. `file` is null when Prometheus has no such file for the model."""
        from database.services import coverage

        result = coverage.line_coverage(self.get_object())
        if result is None:
            return Response({"file": None, "lines": None, "in_download": None, "left_out": {},
                             "complete": None, "reaction_lines": []})
        every = request.query_params.get("lines") == "all"
        body = coverage.summary(result)
        body["reaction_lines"] = [line for line in result["lines"] if every or line["status"] != "in_download"]
        return Response(body)


@extend_schema(tags=["bibliography"])
class SourceViewSet(PermissionsViewSet):
    queryset = models.Source.objects.all()
    serializer_class = serializers.SourceSerializer
    filterset_fields = ["prime_id", "publication_year", "journal_name"]
    search_fields = ["doi", "source_title", "journal_name", "prime_id"]
    ordering_fields = ["publication_year", "prime_id"]


@extend_schema(tags=["bibliography"])
class AuthorViewSet(PermissionsViewSet):
    queryset = models.Author.objects.all()
    serializer_class = serializers.AuthorSerializer
    search_fields = ["firstname", "lastname"]
    ordering_fields = ["lastname", "firstname"]


@extend_schema(tags=["species"])
class StructureViewSet(PermissionsViewSet):
    queryset = models.Structure.objects.all()
    serializer_class = serializers.StructureSerializer
    filterset_fields = ["multiplicity"]
    search_fields = ["smiles", "adjacency_list"]
    ordering_fields = ["id"]
