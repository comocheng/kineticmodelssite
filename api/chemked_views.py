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


# The measurement-type endpoints can also be ordered by the conditions of their datapoint.
_DATAPOINT_ORDERING = ["datapoint__temperature", "datapoint__pressure", "datapoint__equivalence_ratio"]


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
    ignition_delay_quantity = ValueWithUnitSerializer(read_only=True)
    environment_temperature_quantity = ValueWithUnitSerializer(read_only=True)
    global_heat_exchange_coefficient_quantity = ValueWithUnitSerializer(read_only=True)
    exchange_area_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_length_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_diameter_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
    temperature_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
    volumetric_flow_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
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
        # Set by sync_chemked from the ChemKED-database clone (provenance.git_sources), not by clients.
        read_only_fields = ["source_commit"]

    expandable_fields = {
        # The literature source lives in the database app.
        "reference": ("api.serializers.SourceSerializer", {"read_only": True}),
    }


class TimeHistorySerializer(FlexFieldsModelSerializer):
    """A signal measured against time for a datapoint, as the ChemKED ``time-histories``.

    ``values`` are [time, quantity] rows (with an uncertainty column if the file gave one) in
    ``time_units`` and ``quantity_units``, as the YAML export writes them.
    """

    class Meta:
        model = models.TimeHistory
        fields = "__all__"


class VolumeHistorySerializer(FlexFieldsModelSerializer):
    """The ChemKED ``volume-history`` of a datapoint: [time, volume] rows, time first."""

    class Meta:
        model = models.VolumeHistory
        fields = "__all__"


class RCMDataSerializer(FlexFieldsModelSerializer):
    """The ChemKED ``rcm-data`` of a datapoint: the conditions at the end of compression and the
    machine parameters. ``<field>_quantity`` is the file's value and unit, ``<field>`` its SI value
    (K, Pa, s, m)."""

    compressed_temperature_quantity = ValueWithUnitSerializer(read_only=True)
    compressed_pressure_quantity = ValueWithUnitSerializer(read_only=True)
    compression_time_quantity = ValueWithUnitSerializer(read_only=True)
    stroke_quantity = ValueWithUnitSerializer(read_only=True)
    clearance_quantity = ValueWithUnitSerializer(read_only=True)
    compression_ratio_quantity = ValueWithUnitSerializer(read_only=True)

    class Meta:
        model = models.RCMData
        fields = "__all__"

    # by path: the datapoint serializer is defined below and expands to this one
    expandable_fields = {
        "datapoint": ("api.chemked_views.ExperimentDatapointSerializer", {"read_only": True}),
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
        "time_histories": (TimeHistorySerializer, {"read_only": True, "many": True}),
        "volume_history": (VolumeHistorySerializer, {"read_only": True}),
        "rcm_data": (RCMDataSerializer, {"read_only": True}),
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


class IndependentVariableSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.IndependentVariable
        fields = "__all__"


class ConcentrationProfileSerializer(FlexFieldsModelSerializer):
    """A species profile: rows of independent values, amount [and uncertainty]."""

    species = CompositionSpeciesSerializer(read_only=True)

    class Meta:
        model = models.ConcentrationProfile
        fields = "__all__"

    expandable_fields = {
        "measurement": ("api.chemked_views.SpeciationMeasurementSerializer", {"read_only": True}),
    }


class AuxiliaryProfileSerializer(FlexFieldsModelSerializer):
    class Meta:
        model = models.AuxiliaryProfile
        fields = "__all__"

    expandable_fields = {
        "measurement": ("api.chemked_views.SpeciationMeasurementSerializer", {"read_only": True}),
    }


class SpeciationMeasurementSerializer(FlexFieldsModelSerializer):
    """A ChemKED speciation measurement datapoint with its profiles."""

    environment_temperature_quantity = ValueWithUnitSerializer(read_only=True)
    residence_time_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_volume_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_length_quantity = ValueWithUnitSerializer(read_only=True)
    reactor_diameter_quantity = ValueWithUnitSerializer(read_only=True)
    flow_rate_quantity = ValueWithUnitSerializer(read_only=True)
    volumetric_flow_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
    pressure_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
    temperature_in_reference_state_quantity = ValueWithUnitSerializer(read_only=True)
    global_heat_exchange_coefficient_quantity = ValueWithUnitSerializer(read_only=True)
    exchange_area_quantity = ValueWithUnitSerializer(read_only=True)
    laminar_burning_velocity_quantity = ValueWithUnitSerializer(read_only=True)
    timeshift_amount_quantity = ValueWithUnitSerializer(read_only=True)
    independent_variables = IndependentVariableSerializer(many=True, read_only=True)
    concentration_profiles = ConcentrationProfileSerializer(many=True, read_only=True)
    auxiliary_profiles = AuxiliaryProfileSerializer(many=True, read_only=True)

    class Meta:
        model = models.SpeciationMeasurementDatapoint
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
    ordering_fields = ["ignition_delay", *_DATAPOINT_ORDERING, "id"]


@extend_schema(tags=["experimental-data"])
class LaminarBurningVelocityViewSet(ReadOnlyViewSet):
    queryset = models.LaminarBurningVelocityMeasurementDatapoint.objects.all()
    serializer_class = LaminarBurningVelocityDatapointSerializer
    filterset_class = filters.LaminarBurningVelocityFilter
    ordering_fields = ["laminar_burning_velocity", *_DATAPOINT_ORDERING, "id"]


@extend_schema(tags=["experimental-data"])
class RateCoefficientViewSet(ReadOnlyViewSet):
    queryset = models.RateCoefficientDatapoint.objects.all()
    serializer_class = RateCoefficientDatapointSerializer
    filterset_class = filters.RateCoefficientFilter
    search_fields = ["reaction", "method"]
    ordering_fields = [*_DATAPOINT_ORDERING, "id"]


@extend_schema(tags=["experimental-data"])
class SpeciationMeasurementViewSet(ReadOnlyViewSet):
    # Filters across profiles and variables would repeat a datapoint once per match
    queryset = (
        models.SpeciationMeasurementDatapoint.objects
        .prefetch_related(
            "independent_variables", "concentration_profiles__species", "auxiliary_profiles"
        )
        .order_by("id")
        .distinct()
    )
    serializer_class = SpeciationMeasurementSerializer
    filterset_class = filters.SpeciationMeasurementFilter
    ordering_fields = ["residence_time", "reactor_volume", "flow_rate", *_DATAPOINT_ORDERING, "id"]


@extend_schema(tags=["experimental-data"])
class ConcentrationProfileViewSet(ReadOnlyViewSet):
    queryset = models.ConcentrationProfile.objects.select_related("species").order_by("id")
    serializer_class = ConcentrationProfileSerializer
    filterset_class = filters.ConcentrationProfileFilter
    search_fields = ["species__species_name", "species__inchi"]
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class AuxiliaryProfileViewSet(ReadOnlyViewSet):
    queryset = models.AuxiliaryProfile.objects.order_by("id")
    serializer_class = AuxiliaryProfileSerializer
    filterset_class = filters.AuxiliaryProfileFilter
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class TimeHistoryViewSet(ReadOnlyViewSet):
    queryset = models.TimeHistory.objects.order_by("id")
    serializer_class = TimeHistorySerializer
    filterset_class = filters.TimeHistoryFilter
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class VolumeHistoryViewSet(ReadOnlyViewSet):
    queryset = models.VolumeHistory.objects.order_by("id")
    serializer_class = VolumeHistorySerializer
    filterset_class = filters.VolumeHistoryFilter
    ordering_fields = ["id"]


@extend_schema(tags=["experimental-data"])
class RCMDataViewSet(ReadOnlyViewSet):
    queryset = models.RCMData.objects.select_related(
        "compressed_temperature_quantity", "compressed_pressure_quantity", "compression_time_quantity",
        "stroke_quantity", "clearance_quantity", "compression_ratio_quantity",
    ).order_by("id")
    serializer_class = RCMDataSerializer
    filterset_class = filters.RCMDataFilter
    ordering_fields = ["compressed_temperature", "compressed_pressure", "id"]

