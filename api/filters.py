"""django-filter FilterSets for the API.

These power range/equality/relational query parameters on the data endpoints.
Relationships are traversable with Django's ``__`` syntax (e.g. filter
ignition-delay datapoints by ``datapoint__dataset`` or by the species present via
``datapoint__composition__species__cas``). drf-spectacular introspects them, so
every parameter is documented automatically in the schema.
"""

import django_filters as df

from analysis import models as am
from chemked_database import models as cm

# Common relational lookups reused across the measurement-type endpoints. Each
# one hangs off the shared ``datapoint`` relation.
_DATAPOINT_FIELDS = {
    "datapoint": ["exact"],
    "datapoint__dataset": ["exact"],
    "datapoint__temperature": ["gte", "lte"],
    "datapoint__pressure": ["gte", "lte"],
    "datapoint__equivalence_ratio": ["gte", "lte"],
    "datapoint__composition__species__cas": ["exact"],
    "datapoint__composition__species__inchi": ["exact"],
    "datapoint__composition__species__species_name": ["icontains"],
}


class ExperimentDatasetFilter(df.FilterSet):
    class Meta:
        model = cm.ExperimentDataset
        fields = {
            "experiment_type": ["exact"],
            "reference": ["exact"],
            "reference_doi": ["exact", "icontains"],
            "reference_journal": ["icontains"],
            "reference_year": ["exact", "gte", "lte"],
            "file_doi": ["exact"],
            "is_valid": ["exact"],
            "apparatus": ["exact"],
            "apparatus__kind": ["exact"],
            "apparatus__mode": ["exact"],
            # Datasets that contain a given species (by identity).
            "datapoints__composition__species__cas": ["exact"],
            "datapoints__composition__species__species_name": ["icontains"],
        }


class ExperimentDatapointFilter(df.FilterSet):
    class Meta:
        model = cm.ExperimentDatapoint
        fields = {
            "temperature": ["exact", "gte", "lte"],
            "pressure": ["exact", "gte", "lte"],
            "equivalence_ratio": ["exact", "gte", "lte"],
            "residence_time": ["exact", "gte", "lte"],
            "position": ["exact", "gte", "lte"],
            "dataset": ["exact"],
            "dataset__experiment_type": ["exact"],
            "dataset__apparatus__kind": ["exact"],
            # Datapoints whose composition contains a given species.
            "composition__species__cas": ["exact"],
            "composition__species__species_name": ["icontains"],
            "composition__species__inchi": ["exact"],
        }


class CommonPropertiesFilter(df.FilterSet):
    class Meta:
        model = cm.CommonProperties
        fields = {
            "temperature": ["exact", "gte", "lte"],
            "pressure": ["exact", "gte", "lte"],
            "equivalence_ratio": ["exact", "gte", "lte"],
            "ignition_target": ["exact"],
            "ignition_type": ["exact"],
            "dataset": ["exact"],
        }


class IgnitionDelayFilter(df.FilterSet):
    class Meta:
        model = cm.IgnitionDelayDatapoint
        fields = {
            "ignition_delay": ["exact", "gte", "lte"],
            "first_stage_ignition_delay": ["gte", "lte"],
            "ignition_target": ["exact"],
            "ignition_type": ["exact"],
            **_DATAPOINT_FIELDS,
        }


class LaminarBurningVelocityFilter(df.FilterSet):
    class Meta:
        model = cm.LaminarBurningVelocityMeasurementDatapoint
        fields = {
            "laminar_burning_velocity": ["exact", "gte", "lte"],
            "stretch": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class RateCoefficientFilter(df.FilterSet):
    class Meta:
        model = cm.RateCoefficientDatapoint
        fields = {
            "measurement_type": ["exact"],
            "reaction_order": ["exact"],
            **_DATAPOINT_FIELDS,
        }


class ConcentrationTimeProfileFilter(df.FilterSet):
    class Meta:
        model = cm.ConcentrationTimeProfileMeasurementDatapoint
        fields = {
            "timeshift_type": ["exact"],
            **_DATAPOINT_FIELDS,
        }


class JetStirredReactorFilter(df.FilterSet):
    class Meta:
        model = cm.JetStirredReactorMeasurementDatapoint
        fields = {
            "environment_temperature": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class OutletConcentrationFilter(df.FilterSet):
    class Meta:
        model = cm.OutletConcentrationMeasurementDatapoint
        fields = {
            "residence_time": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class BurnerStabilizedFlameFilter(df.FilterSet):
    class Meta:
        model = cm.BurnerStabilizedFlameSpeciationMeasurementDatapoint
        fields = {
            "distance": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class CompositionSpeciesFilter(df.FilterSet):
    class Meta:
        model = cm.CompositionSpecies
        fields = {
            "species_name": ["exact", "icontains"],
            "cas": ["exact"],
            "inchi": ["exact"],
            "smiles": ["exact"],
            "amount": ["gte", "lte"],
            "composition": ["exact"],
        }


class SimulationRunFilter(df.FilterSet):
    class Meta:
        model = am.SimulationRun
        fields = {
            "status": ["exact"],
            "triggered_by": ["exact"],
            "kinetic_model": ["exact"],
            "dataset": ["exact"],
            "dataset__experiment_type": ["exact"],
        }


class ModelDatasetCoverageFilter(df.FilterSet):
    class Meta:
        model = am.ModelDatasetCoverage
        fields = {
            "has_successful_run": ["exact"],
            "is_outdated": ["exact"],
            "needs_rerun": ["exact"],
            "latest_error_function": ["gte", "lte"],
            "latest_deviation": ["gte", "lte"],
            "kinetic_model": ["exact"],
            "dataset": ["exact"],
        }


class DatapointResultFilter(df.FilterSet):
    class Meta:
        model = am.DatapointResult
        fields = {
            "temperature": ["gte", "lte"],
            "pressure": ["gte", "lte"],
            "success": ["exact"],
            "error_value": ["gte", "lte"],
            "simulation_result": ["exact"],
            "datapoint": ["exact"],
            "datapoint__dataset": ["exact"],
        }
