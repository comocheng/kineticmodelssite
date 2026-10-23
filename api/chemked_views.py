"""Read-only API for the ChemKED experimental-data layer (``chemked_database``).

Experimental datasets, datapoints, and the per-measurement-type detail tables
are exposed as read-only endpoints. New experimental data is contributed through
the contribution endpoints (see ``api/contribution_views.py``) and the PR/CI
workflow, not written directly through these endpoints.

High-value relations (quantities, apparatus, authors, composition) are nested
inline. Foreign-key relations to parents (a datapoint's ``dataset``, a dataset's
``reference``, a measurement's ``datapoint``) are returned as IDs by default and
can be pulled inline on demand with ``?expand=`` (drf-flex-fields); ``?fields=``
and ``?omit=`` trim the response.
"""

from drf_spectacular.utils import extend_schema
from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from chemked_database import models
from api import filters


class ReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve only. Experimental data is contributed via the PR workflow."""

    permission_classes = [AllowAny]


# ---------------------------------------------------------------------------
# Leaf / nested serializers (defined first so composites can reference them)
# ---------------------------------------------------------------------------
class ValueWithUnitSerializer(FlexFieldsModelSerializer):
    """A measured quantity: value, units, and uncertainty metadata."""

    class Meta:
        model = models.ValueWithUnit
        fields = "__all__"


class ApparatusSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.Apparatus
        fields = "__all__"


class FileAuthorSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.FileAuthor
        fields = "__all__"


class ReferenceAuthorSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.ReferenceAuthor
        fields = "__all__"


class CompositionSpeciesSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.CompositionSpecies
        fields = "__all__"


class CompositionSerializer(FlexFieldsModelSerializer):
    # related_name on CompositionSpecies.composition is "species"
    species = CompositionSpeciesSerializer(many=True, read_only=True)

    class Meta:
        model = models.Composition
        fields = "__all__"


class CommonPropertiesSerializer(FlexFieldsModelSerializer):
    pressure_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_rise_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_volume_quantity = ValueWithUnitSerializer(read_only=True)
    residence_time_quantity = ValueWithUnitSerializer(read_only=True)
    equivalence_ratio_quantity = ValueWithUnitSerializer(read_only=True)
    temperature_quantity = ValueWithUnitSerializer(read_only=True)
    flow_rate_quantity = ValueWithUnitSerializer(read_only=True)
    laminar_burning_velocity_quantity = ValueWithUnitSerializer(read_only=True)
    composition = CompositionSerializer(read_only=True)

    class Meta:
        model = models.CommonProperties
        fields = "__all__"


# ---------------------------------------------------------------------------
# Top-level resource serializers
# ---------------------------------------------------------------------------
class ExperimentDatasetSerializer(FlexFieldsModelSerializer):
    apparatus = ApparatusSerializer(read_only=True)
    file_authors = FileAuthorSerializer(many=True, read_only=True)
    reference_authors = ReferenceAuthorSerializer(many=True, read_only=True)
    common_properties = CommonPropertiesSerializer(read_only=True)

    class Meta:
        model = models.ExperimentDataset
        fields = "__all__"

    expandable_fields = {
        # The literature source lives in the database app.
        "reference": ("api.serializers.SourceSerializer", {"read_only": True}),
    }


class ExperimentDatapointSerializer(FlexFieldsModelSerializer):
    temperature_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_quantity = ValueWithUnitSerializer(read_only=True)
    equivalence_ratio_quantity = ValueWithUnitSerializer(read_only=True)
    composition = CompositionSerializer(read_only=True)

    class Meta:
        model = models.ExperimentDatapoint
        fields = "__all__"

    expandable_fields = {
        "dataset": (ExperimentDatasetSerializer, {"read_only": True}),
    }


# Each measurement-type record one-to-one with a datapoint, expandable to it.
_DATAPOINT_EXPAND = {"datapoint": (ExperimentDatapointSerializer, {"read_only": True})}


class IgnitionDelayDatapointSerializer(FlexFieldsModelSerializer):
    ignition_delay_quantity = ValueWithUnitSerializer(read_only=True)
    first_stage_ignition_delay_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_rise_quantity = ValueWithUnitSerializer(read_only=True)

    class Meta:
        model = models.IgnitionDelayDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class LaminarBurningVelocityDatapointSerializer(FlexFieldsModelSerializer):
    laminar_burning_velocity_quantity = ValueWithUnitSerializer(read_only=True)
    stretch_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_rise_quantity = ValueWithUnitSerializer(read_only=True)

    class Meta:
        model = models.LaminarBurningVelocityMeasurementDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class RateCoefficientDatapointSerializer(FlexFieldsModelSerializer):
    rate_coefficient_quantity = ValueWithUnitSerializer(read_only=True)

    class Meta:
        model = models.RateCoefficientDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class ConcentrationTimeProfileDatapointSerializer(FlexFieldsModelSerializer):
    timeshift_amount_quantity = ValueWithUnitSerializer(read_only=True)

    class Meta:
        model = models.ConcentrationTimeProfileMeasurementDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class JetStirredReactorDatapointSerializer(FlexFieldsModelSerializer):
    environment_temperature_quantity = ValueWithUnitSerializer(read_only=True)
    measured_composition = CompositionSerializer(read_only=True)

    class Meta:
        model = models.JetStirredReactorMeasurementDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class OutletConcentrationDatapointSerializer(FlexFieldsModelSerializer):
    residence_time_quantity = ValueWithUnitSerializer(read_only=True)
    volumetric_flow_quantity = ValueWithUnitSerializer(read_only=True)
    measured_composition = CompositionSerializer(read_only=True)
    initial_composition = CompositionSerializer(read_only=True)

    class Meta:
        model = models.OutletConcentrationMeasurementDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


class BurnerStabilizedFlameDatapointSerializer(FlexFieldsModelSerializer):
    distance_quantity = ValueWithUnitSerializer(read_only=True)
    flow_rate_quantity = ValueWithUnitSerializer(read_only=True)
    measured_composition = CompositionSerializer(read_only=True)

    class Meta:
        model = models.BurnerStabilizedFlameSpeciationMeasurementDatapoint
        fields = "__all__"

    expandable_fields = _DATAPOINT_EXPAND


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------
@extend_schema(tags=["experimental-data"])
class ExperimentDatasetViewSet(ReadOnlyViewSet):
    queryset = models.ExperimentDataset.objects.all()
    serializer_class = ExperimentDatasetSerializer
    filterset_class = filters.ExperimentDatasetFilter
    search_fields = ["reference_doi", "reference_journal", "file_doi", "experiment_type"]
    ordering_fields = ["reference_year", "created_at", "id"]


@extend_schema(tags=["experimental-data"])
class ExperimentDatapointViewSet(ReadOnlyViewSet):
    queryset = models.ExperimentDatapoint.objects.all()
    serializer_class = ExperimentDatapointSerializer
    filterset_class = filters.ExperimentDatapointFilter
    ordering_fields = ["temperature", "pressure", "equivalence_ratio", "id"]


@extend_schema(tags=["experimental-data"])
class ApparatusViewSet(ReadOnlyViewSet):
    queryset = models.Apparatus.objects.all()
    serializer_class = ApparatusSerializer
    filterset_fields = ["kind", "mode", "institution", "facility"]
    search_fields = ["institution", "facility"]
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class CommonPropertiesViewSet(ReadOnlyViewSet):
    queryset = models.CommonProperties.objects.all()
    serializer_class = CommonPropertiesSerializer
    filterset_class = filters.CommonPropertiesFilter
    ordering_fields = ["temperature", "pressure", "id"]


@extend_schema(tags=["experimental-data"])
class CompositionViewSet(ReadOnlyViewSet):
    queryset = models.Composition.objects.all()
    serializer_class = CompositionSerializer
    filterset_fields = ["kind"]
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class CompositionSpeciesViewSet(ReadOnlyViewSet):
    queryset = models.CompositionSpecies.objects.all()
    serializer_class = CompositionSpeciesSerializer
    filterset_class = filters.CompositionSpeciesFilter
    search_fields = ["species_name", "chem_name", "cas", "inchi", "smiles"]
    ordering_fields = ["amount", "id"]


@extend_schema(tags=["experimental-data"])
class IgnitionDelayViewSet(ReadOnlyViewSet):
    queryset = models.IgnitionDelayDatapoint.objects.all()
    serializer_class = IgnitionDelayDatapointSerializer
    filterset_class = filters.IgnitionDelayFilter
    ordering_fields = ["ignition_delay", "id"]


@extend_schema(tags=["experimental-data"])
class LaminarBurningVelocityViewSet(ReadOnlyViewSet):
    queryset = models.LaminarBurningVelocityMeasurementDatapoint.objects.all()
    serializer_class = LaminarBurningVelocityDatapointSerializer
    filterset_class = filters.LaminarBurningVelocityFilter
    ordering_fields = ["laminar_burning_velocity", "id"]


@extend_schema(tags=["experimental-data"])
class RateCoefficientViewSet(ReadOnlyViewSet):
    queryset = models.RateCoefficientDatapoint.objects.all()
    serializer_class = RateCoefficientDatapointSerializer
    filterset_class = filters.RateCoefficientFilter
    search_fields = ["reaction", "method"]
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class ConcentrationTimeProfileViewSet(ReadOnlyViewSet):
    queryset = models.ConcentrationTimeProfileMeasurementDatapoint.objects.all()
    serializer_class = ConcentrationTimeProfileDatapointSerializer
    filterset_class = filters.ConcentrationTimeProfileFilter
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class JetStirredReactorViewSet(ReadOnlyViewSet):
    queryset = models.JetStirredReactorMeasurementDatapoint.objects.all()
    serializer_class = JetStirredReactorDatapointSerializer
    filterset_class = filters.JetStirredReactorFilter
    ordering_fields = ["environment_temperature", "id"]


@extend_schema(tags=["experimental-data"])
class OutletConcentrationViewSet(ReadOnlyViewSet):
    queryset = models.OutletConcentrationMeasurementDatapoint.objects.all()
    serializer_class = OutletConcentrationDatapointSerializer
    filterset_class = filters.OutletConcentrationFilter
    ordering_fields = ["residence_time", "id"]


@extend_schema(tags=["experimental-data"])
class BurnerStabilizedFlameViewSet(ReadOnlyViewSet):
    queryset = models.BurnerStabilizedFlameSpeciationMeasurementDatapoint.objects.all()
    serializer_class = BurnerStabilizedFlameDatapointSerializer
    filterset_class = filters.BurnerStabilizedFlameFilter
    ordering_fields = ["distance", "id"]
