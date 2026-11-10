"""FAIR JSON-LD metadata endpoints.

Public, read-only views that emit linked-data (schema.org / PROV / Prometheus
ontology) representations of catalog records. These complement the regular DRF
resource endpoints: the same record is available as JSON-LD at
``<resource>/<pk>/metadata/`` for harvesters and FAIR tooling.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from chemked_database.models import ExperimentDataset
from database.models import KineticModel, Source

from api.fair_metadata import (
    catalog_jsonld,
    experiment_dataset_jsonld,
    kinetic_model_jsonld,
    source_jsonld,
)


@extend_schema(
    tags=["metadata"],
    description="FAIR data catalog description (JSON-LD).",
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_metadata(request):
    return Response(catalog_jsonld())


@extend_schema(
    tags=["metadata"],
    description="Source as schema.org/PROV JSON-LD.",
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def source_metadata(request, pk):
    source = get_object_or_404(Source.objects.prefetch_related("authors__person"), pk=pk)
    return Response(source_jsonld(source))


@extend_schema(
    tags=["metadata"],
    description="Kinetic model as schema.org/PROV JSON-LD.",
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def kinetic_model_metadata(request, pk):
    model = get_object_or_404(KineticModel.objects.select_related("license", "source"), pk=pk)
    return Response(kinetic_model_jsonld(model))


@extend_schema(
    tags=["metadata"],
    description="Experiment dataset as schema.org/PROV JSON-LD.",
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def experiment_dataset_metadata(request, pk):
    qs = ExperimentDataset.objects.select_related(
        "license", "apparatus__institution_ref"
    ).prefetch_related("file_authors__person")
    dataset = get_object_or_404(qs, pk=pk)
    return Response(experiment_dataset_jsonld(dataset))
