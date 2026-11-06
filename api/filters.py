"""django-filter FilterSets for the API.

These power range/equality/relational query parameters on the data endpoints.
Relationships are traversable with Django's ``__`` syntax (e.g. filter
ignition-delay datapoints by ``datapoint__dataset`` or by the species present via
``datapoint__composition__species__cas``). drf-spectacular introspects them, so
every parameter is documented automatically in the schema.

Conventions shared by the endpoints:

* A record is listed once, however many related rows match a filter.
* ``<field>__in=1,2,3`` selects the records whose field has one of the values.
* ``species``, ``inchi`` and ``cas`` select by the mixture of a datapoint: its own
  composition, or the common-properties composition of its dataset when it has none.
  Repeat the parameter to require every value in the same mixture.
* ``has_<relation>=true|false`` selects the records with or without related rows.
"""

import re

from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Exists, OuterRef, Q
from django.db.models.constants import LOOKUP_SEP
from django.http import QueryDict
import django_filters as df
from django_filters.rest_framework import BooleanFilter
from django_filters.rest_framework import FilterSet as RestFilterSet

from analysis import models as am
from chemked_database import models as cm
from database import models as dm


def _spans_many(model, path):
    """True if the lookup path crosses a to-many relation, so one record can match many rows."""
    for part in path.split(LOOKUP_SEP):
        try:
            field = model._meta.get_field(part)
        except FieldDoesNotExist:
            return False
        if field.many_to_many or field.one_to_many:
            return True
        if not field.is_relation:
            return False
        model = field.related_model
    return False


class FilterSet(RestFilterSet):
    """Base FilterSet: a record is listed once, however many related rows match the filters."""

    def filter_queryset(self, queryset):
        filtered = super().filter_queryset(queryset)
        used = [name for name in self.filters if name in self.data]
        if any(_spans_many(queryset.model, self.filters[name].field_name) for name in used):
            return queryset.filter(pk__in=filtered.values("pk"))
        return filtered


class _TextValuesField(forms.MultipleChoiceField):
    """The values of a repeated text parameter; any text is valid."""

    def valid_value(self, value):
        return True


class TextValuesFilter(df.MultipleChoiceFilter):
    """A text parameter that can be repeated. Text such as an InChI can contain commas, so the
    values are not comma-separated."""

    field_class = _TextValuesField


class HasFilter(BooleanFilter):
    """``true`` selects the records with at least one related row at ``field_name``, ``false``
    the records with none."""

    def filter(self, qs, value):
        if value is None:
            return qs
        lookup = {f"{self.field_name}__isnull": False}
        return qs.filter(**lookup) if value else qs.exclude(**lookup)


# ---------------------------------------------------------------------------
# The mixture of a datapoint
# ---------------------------------------------------------------------------
def _bare_inchi(value):
    """CompositionSpecies stores the InChI without the ``InChI=`` prefix; Isomer stores it with."""
    value = value.strip()
    return value[len("InChI="):] if value.startswith("InChI=") else value


# RMG writes the unpaired electrons (/u) and lone pairs (/lp) of a structure as extra InChI
# layers; a standard InChI, as in ChemKED, has neither.
_RMG_LAYERS = re.compile(r"/(?:u|lp)[^/]*")


def _inchi_forms(inchi):
    """The forms under which a component can store ``inchi``: bare, with the ``InChI=`` prefix,
    and both again without RMG's layers."""
    bare = _bare_inchi(inchi)
    forms = {bare, _RMG_LAYERS.sub("", bare)}
    return sorted(forms | {f"InChI={f}" for f in forms})


def _species_component(species):
    """Mixture components that are the species record: linked to it, or with its standard InChI.

    A standard InChI has no spin layer, so records that differ only in their spin (triplet O2
    and singlet O2) match the same components, whichever of them a component is linked to. An
    InChI does not tell an electronic state from the ground state either, so an excited-state
    record matches only the components linked to it, and a ground-state record does not match
    a component linked to an excited-state record.
    """
    q = Q(database_species=species)
    if not species.electronic_state:
        inchis = [i for i in species.isomers.values_list("inchi", flat=True) if i]
        forms = sorted({f for i in inchis for f in _inchi_forms(i)})
        if forms:
            q |= Q(inchi__in=forms) & ~Q(database_species__electronic_state__gt="")
    return q


def _inchi_component(inchi):
    return Q(inchi__in=_inchi_forms(inchi))


def _cas_component(cas):
    return Q(cas=cas.strip())


def _compositions_with_all(components):
    """Compositions that have a component matching each Q in ``components``."""
    compositions = cm.Composition.objects.all()
    for q in components:
        compositions = compositions.filter(
            Exists(cm.CompositionSpecies.objects.filter(q, composition=OuterRef("pk")))
        )
    return compositions


class MixtureFilterSet(FilterSet):
    """``species``, ``inchi`` and ``cas`` on the mixture of a datapoint. ``datapoint_path`` is the
    path from the filtered model to its ExperimentDatapoint."""

    datapoint_path = ""

    species = df.ModelMultipleChoiceFilter(
        queryset=dm.Species.objects.all(),
        method="filter_species",
        help_text="ID of a species record (from /api/species/) in the mixture, matched by its "
                  "standard InChI; records that differ only in spin (triplet and singlet O2) "
                  "match the same components. Repeat the parameter to require every species "
                  "given in the same mixture.",
    )
    inchi = TextValuesFilter(
        method="filter_inchi",
        help_text="InChI of a mixture component, with or without the 'InChI=' prefix and RMG's "
                  "/u and /lp layers; repeat the parameter to require every component given in "
                  "the same mixture.",
    )
    cas = TextValuesFilter(
        method="filter_cas",
        help_text="CAS number of a mixture component; repeat the parameter to require every "
                  "component given in the same mixture.",
    )

    # The type hints give drf-spectacular the type of one value of each parameter.
    def filter_species(self, queryset, name, value: int):
        return self._filter_mixture(queryset, [_species_component(s) for s in value])

    def filter_inchi(self, queryset, name, value: str):
        return self._filter_mixture(queryset, [_inchi_component(v) for v in value])

    def filter_cas(self, queryset, name, value: str):
        return self._filter_mixture(queryset, [_cas_component(v) for v in value])

    def _filter_mixture(self, queryset, components):
        if not components:
            return queryset
        compositions = _compositions_with_all(components)
        p = self.datapoint_path
        own = Q(**{f"{p}composition__in": compositions})
        common = Q(**{f"{p}composition__isnull": True,
                      f"{p}dataset__common_properties__composition__in": compositions})
        return queryset.filter(own | common)


# Common relational lookups reused across the measurement-type endpoints. Each
# one hangs off the shared ``datapoint`` relation.
_DATAPOINT_FIELDS = {
    "datapoint": ["exact", "in"],
    "datapoint__dataset": ["exact", "in"],
    "datapoint__temperature": ["gte", "lte"],
    "datapoint__pressure": ["gte", "lte"],
    "datapoint__equivalence_ratio": ["gte", "lte"],
    "datapoint__composition__species__cas": ["exact"],
    "datapoint__composition__species__inchi": ["exact"],
    "datapoint__composition__species__species_name": ["icontains"],
}


class MeasurementFilterSet(MixtureFilterSet):
    """A measurement-type record, one-to-one with a datapoint."""

    datapoint_path = "datapoint__"


class ExperimentDatapointFilter(MixtureFilterSet):
    has_time_histories = HasFilter(
        field_name="time_histories", help_text="true: datapoints with a time history."
    )
    has_volume_history = HasFilter(
        field_name="volume_history", help_text="true: datapoints with a volume history."
    )

    class Meta:
        model = cm.ExperimentDatapoint
        fields = {
            "id": ["in"],
            "temperature": ["exact", "gte", "lte", "isnull"],
            "pressure": ["exact", "gte", "lte"],
            "equivalence_ratio": ["exact", "gte", "lte", "isnull"],
            "residence_time": ["exact", "gte", "lte"],
            "position": ["exact", "gte", "lte"],
            "dataset": ["exact", "in"],
            "dataset__experiment_type": ["exact", "in"],
            "dataset__apparatus__kind": ["exact", "in"],
            # Datapoints whose own composition contains a given species.
            "composition__species__cas": ["exact"],
            "composition__species__species_name": ["icontains"],
            "composition__species__inchi": ["exact"],
        }


# The dataset filters that one datapoint must meet together.
_ONE_DATAPOINT = (
    "species", "inchi", "cas",
    "temperature__gte", "temperature__lte", "pressure__gte", "pressure__lte",
    "equivalence_ratio__gte", "equivalence_ratio__lte",
)


class ExperimentDatasetFilter(FilterSet):
    # These conditions apply to one datapoint: a dataset matches when one of its datapoints
    # meets every condition given (see filter_queryset).
    species = df.ModelMultipleChoiceFilter(
        queryset=dm.Species.objects.all(),
        method="filter_species_on_one_datapoint",
        help_text="Datasets with a datapoint whose mixture contains this species record (ID "
                  "from /api/species/); repeat the parameter to require every species given.",
    )
    inchi = TextValuesFilter(
        method="filter_text_on_one_datapoint",
        help_text="Datasets with a datapoint whose mixture contains a component with this InChI; "
                  "repeat the parameter to require every component given.",
    )
    cas = TextValuesFilter(
        method="filter_text_on_one_datapoint",
        help_text="Datasets with a datapoint whose mixture contains a component with this CAS "
                  "number; repeat the parameter to require every component given.",
    )
    temperature__gte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this temperature or above (K).",
    )
    temperature__lte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this temperature or below (K).",
    )
    pressure__gte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this pressure or above (Pa).",
    )
    pressure__lte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this pressure or below (Pa).",
    )
    equivalence_ratio__gte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this equivalence ratio or above.",
    )
    equivalence_ratio__lte = df.NumberFilter(
        method="filter_on_one_datapoint",
        help_text="Datasets with a datapoint at this equivalence ratio or below.",
    )

    has_time_histories = HasFilter(
        field_name="datapoints__time_histories",
        help_text="true: datasets with a time history in one of their datapoints.",
    )
    has_volume_history = HasFilter(
        field_name="datapoints__volume_history",
        help_text="true: datasets with a volume history in one of their datapoints.",
    )
    has_common_properties = HasFilter(
        field_name="common_properties", help_text="true: datasets with common properties."
    )
    has_reference = HasFilter(
        field_name="reference", help_text="true: datasets linked to a source record."
    )
    has_license = HasFilter(field_name="license", help_text="true: datasets with a licence.")

    class Meta:
        model = cm.ExperimentDataset
        fields = {
            "id": ["in"],
            "experiment_type": ["exact", "in"],
            "reference": ["exact"],
            "reference_doi": ["exact", "icontains"],
            "reference_journal": ["icontains"],
            "reference_year": ["exact", "gte", "lte"],
            "file_doi": ["exact"],
            "is_valid": ["exact"],
            "apparatus": ["exact"],
            "apparatus__kind": ["exact", "in"],
            "apparatus__mode": ["exact"],
            # Datasets that contain a given species (by identity).
            "datapoints__composition__species__cas": ["exact"],
            "datapoints__composition__species__species_name": ["icontains"],
        }

    # Applied together in filter_queryset. The type hints give drf-spectacular the value types.
    def filter_on_one_datapoint(self, queryset, name, value):
        return queryset

    def filter_species_on_one_datapoint(self, queryset, name, value: int):
        return queryset

    def filter_text_on_one_datapoint(self, queryset, name, value: str):
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        conditions = QueryDict(mutable=True)
        for name in _ONE_DATAPOINT:
            if name in self.data:
                conditions.setlist(name, self.data.getlist(name))
        if conditions:
            points = ExperimentDatapointFilter(
                conditions, queryset=cm.ExperimentDatapoint.objects.all()
            ).qs
            queryset = queryset.filter(Exists(points.filter(dataset=OuterRef("pk"))))
        return queryset


class CommonPropertiesFilter(FilterSet):
    has_ignition_type = BooleanFilter(
        field_name="ignition_type", method="filter_has_text",
        help_text="true: common properties with an ignition type.",
    )
    has_ignition_target = BooleanFilter(
        field_name="ignition_target", method="filter_has_text",
        help_text="true: common properties with an ignition target.",
    )

    class Meta:
        model = cm.CommonProperties
        fields = {
            "temperature": ["exact", "gte", "lte"],
            "pressure": ["exact", "gte", "lte"],
            "pressure_rise": ["isnull"],
            "equivalence_ratio": ["exact", "gte", "lte"],
            "ignition_target": ["exact", "in"],
            "ignition_type": ["exact", "in"],
            "dataset": ["exact", "in"],
        }

    def filter_has_text(self, queryset, name, value):
        given = Q(**{f"{name}__gt": ""})
        return queryset.filter(given) if value else queryset.exclude(given)


class IgnitionDelayFilter(MeasurementFilterSet):
    has_ignition_type = BooleanFilter(
        field_name="ignition_type", method="filter_given",
        help_text="true: datapoints with an ignition type of their own or in the common "
                  "properties of their dataset.",
    )
    has_ignition_target = BooleanFilter(
        field_name="ignition_target", method="filter_given",
        help_text="true: datapoints with an ignition target of their own or in the common "
                  "properties of their dataset.",
    )
    has_pressure_rise = BooleanFilter(
        field_name="pressure_rise", method="filter_given",
        help_text="true: datapoints with a pressure rise of their own or in the common "
                  "properties of their dataset.",
    )

    class Meta:
        model = cm.IgnitionDelayDatapoint
        fields = {
            "ignition_delay": ["exact", "gte", "lte"],
            "first_stage_ignition_delay": ["gte", "lte", "isnull"],
            "ignition_target": ["exact", "in"],
            "ignition_type": ["exact", "in"],
            **_DATAPOINT_FIELDS,
        }

    def filter_given(self, queryset, name, value):
        # A text field without a value is "", a number field is null.
        common = f"datapoint__dataset__common_properties__{name}"
        if name == "pressure_rise":
            given = Q(**{f"{name}__isnull": False}) | Q(**{f"{common}__isnull": False})
        else:
            given = Q(**{f"{name}__gt": ""}) | Q(**{f"{common}__gt": ""})
        given_pks = queryset.model.objects.filter(given).values("pk")
        return queryset.filter(pk__in=given_pks) if value else queryset.exclude(pk__in=given_pks)


class LaminarBurningVelocityFilter(MeasurementFilterSet):
    class Meta:
        model = cm.LaminarBurningVelocityMeasurementDatapoint
        fields = {
            "laminar_burning_velocity": ["exact", "gte", "lte"],
            "stretch": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class RateCoefficientFilter(MeasurementFilterSet):
    class Meta:
        model = cm.RateCoefficientDatapoint
        fields = {
            "measurement_type": ["exact"],
            "reaction_order": ["exact"],
            **_DATAPOINT_FIELDS,
        }


class SpeciationMeasurementFilter(MeasurementFilterSet):
    class Meta:
        model = cm.SpeciationMeasurementDatapoint
        fields = {
            "datapoint__dataset__apparatus__kind": ["exact", "in"],
            # Datapoints swept against a variable, or measuring a species
            "independent_variables__name": ["exact"],
            "concentration_profiles__species__species_name": ["exact", "icontains"],
            "concentration_profiles__species__inchi": ["exact"],
            "concentration_profiles__quantity_units": ["exact"],
            "residence_time": ["gte", "lte"],
            "reactor_volume": ["gte", "lte"],
            "flow_rate": ["gte", "lte"],
            "environment_temperature": ["gte", "lte"],
            **_DATAPOINT_FIELDS,
        }


class ConcentrationProfileFilter(FilterSet):
    class Meta:
        model = cm.ConcentrationProfile
        fields = {
            "measurement": ["exact", "in"],
            "measurement__datapoint": ["exact", "in"],
            "measurement__datapoint__dataset": ["exact", "in"],
            "measurement__datapoint__dataset__apparatus__kind": ["exact"],
            "species__species_name": ["exact", "icontains"],
            "species__inchi": ["exact"],
            "quantity_units": ["exact"],
            "uncertainty_type": ["exact"],
            "evaluated_standard_deviation_type": ["exact"],
        }


class AuxiliaryProfileFilter(FilterSet):
    class Meta:
        model = cm.AuxiliaryProfile
        fields = {
            "measurement": ["exact", "in"],
            "measurement__datapoint__dataset": ["exact", "in"],
            "profile_type": ["exact"],
            "independent_name": ["exact"],
        }


class TimeHistoryFilter(FilterSet):
    class Meta:
        model = cm.TimeHistory
        fields = {
            "datapoint": ["exact", "in"],
            "datapoint__dataset": ["exact", "in"],
            "history_type": ["exact", "in"],
        }


class VolumeHistoryFilter(FilterSet):
    class Meta:
        model = cm.VolumeHistory
        fields = {
            "datapoint": ["exact", "in"],
            "datapoint__dataset": ["exact", "in"],
        }


class KineticModelFilter(FilterSet):
    # The species list of a model links each of its species names to a species record, so a
    # species ID from /api/species/ selects the models that contain that species.
    species = df.ModelMultipleChoiceFilter(
        field_name="speciesname__species",
        queryset=dm.Species.objects.all(),
        conjoined=True,
        help_text="ID of a species record (from /api/species/); repeat the parameter to select "
                  "the models that contain every species given.",
    )

    class Meta:
        model = dm.KineticModel
        fields = {"id": ["in"], "prime_id": ["exact"], "source": ["exact"]}


class CompositionSpeciesFilter(FilterSet):
    class Meta:
        model = cm.CompositionSpecies
        fields = {
            "species_name": ["exact", "icontains"],
            "cas": ["exact"],
            "inchi": ["exact"],
            "smiles": ["exact"],
            "amount": ["gte", "lte"],
            "composition": ["exact", "in"],
        }


class SimulationRunFilter(FilterSet):
    class Meta:
        model = am.SimulationRun
        fields = {
            "status": ["exact"],
            "triggered_by": ["exact"],
            "kinetic_model": ["exact", "in"],
            "dataset": ["exact", "in"],
            "dataset__experiment_type": ["exact"],
        }


class ModelDatasetCoverageFilter(FilterSet):
    class Meta:
        model = am.ModelDatasetCoverage
        fields = {
            "has_successful_run": ["exact"],
            "is_outdated": ["exact"],
            "needs_rerun": ["exact"],
            "latest_error_function": ["gte", "lte"],
            "latest_deviation": ["gte", "lte"],
            "kinetic_model": ["exact", "in"],
            "dataset": ["exact", "in"],
        }


class DatapointResultFilter(FilterSet):
    class Meta:
        model = am.DatapointResult
        fields = {
            "temperature": ["gte", "lte"],
            "pressure": ["gte", "lte"],
            "success": ["exact"],
            "error_value": ["gte", "lte"],
            "simulation_result": ["exact"],
            "datapoint": ["exact", "in"],
            "datapoint__dataset": ["exact", "in"],
        }


# ---------------------------------------------------------------------------
# Species, reactions, rate records and thermochemistry of the kinetic models
# ---------------------------------------------------------------------------
class SpeciesFilter(FilterSet):
    inchi = df.CharFilter(
        field_name="isomers__inchi", method="filter_inchi",
        help_text="Exact InChI of an isomer, with or without 'InChI='. A standard InChI also matches "
                  "the records that add RMG's /u and /lp layers (for example both spin states of O2); "
                  "an InChI with those layers matches that record only.")
    has_electronic_state = df.BooleanFilter(
        field_name="electronic_state", method="filter_has_electronic_state",
        help_text="true: records with an electronic-state label, such as the excited OH* and CH*; "
                  "false: records without one. Spin states are in the structures' multiplicity.")
    multiplicity = df.NumberFilter(
        field_name="isomers__structure__multiplicity",
        help_text="Spin multiplicity of a structure of the species, for example 3 for triplet O2.")
    kinetic_model = df.ModelMultipleChoiceFilter(
        field_name="speciesname__kinetic_model", queryset=dm.KineticModel.objects.all(),
        help_text="ID of a kinetic model; repeat for the species of any of the models given.")

    class Meta:
        model = dm.Species
        fields = {"id": ["in"], "prime_id": ["exact"], "cas_number": ["exact"],
                  "isomers__formula": ["exact"], "electronic_state": ["exact"]}

    def filter_inchi(self, queryset, name, value: str):
        bare = _bare_inchi(value)
        standard = _RMG_LAYERS.sub("", bare)
        if standard != bare:  # the client gave RMG's layers: that record only
            return queryset.filter(isomers__inchi__in=[bare, f"InChI={bare}"])
        q = Q(isomers__inchi__in=[standard, f"InChI={standard}"])
        for prefix in ("InChI=", ""):
            for layer in ("/u", "/lp"):
                q |= Q(isomers__inchi__startswith=f"{prefix}{standard}{layer}")
        return queryset.filter(q)

    def filter_has_electronic_state(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.exclude(electronic_state="") if value else queryset.filter(electronic_state="")


class ReactionFilter(FilterSet):
    species = df.ModelMultipleChoiceFilter(
        field_name="species", queryset=dm.Species.objects.all(), conjoined=True,
        help_text="ID of a species record; repeat for the reactions that contain every species given.")
    kinetic_model = df.ModelMultipleChoiceFilter(
        field_name="kinetics__kineticmodel", queryset=dm.KineticModel.objects.all(),
        help_text="ID of a kinetic model; repeat for the reactions of any of the models given.")
    canonical_key = df.CharFilter(
        field_name="canonical_key",
        help_text="Direction-insensitive identity: selects a reaction and the record of its reverse.")

    class Meta:
        model = dm.Reaction
        fields = {"id": ["in"], "prime_id": ["exact"], "reversible": ["exact"], "layer": ["exact", "in"]}


class KineticsFilter(FilterSet):
    kinetic_model = df.ModelMultipleChoiceFilter(
        field_name="kineticmodel", queryset=dm.KineticModel.objects.all(),
        help_text="ID of a kinetic model; repeat for the rate records of any of the models given.")
    species = df.ModelMultipleChoiceFilter(
        field_name="reaction__species", queryset=dm.Species.objects.all(), conjoined=True,
        help_text="ID of a species record; repeat for the rate records of reactions that contain "
                  "every species given.")
    canonical_key = df.CharFilter(
        field_name="reaction__canonical_key",
        help_text="Rate records of a reaction in either direction (the reaction's canonical_key).")

    class Meta:
        model = dm.Kinetics
        fields = {"id": ["in"], "reaction": ["exact", "in"], "reverse": ["exact"]}


class ThermoFilter(FilterSet):
    kinetic_model = df.ModelMultipleChoiceFilter(
        field_name="kineticmodel", queryset=dm.KineticModel.objects.all(),
        help_text="ID of a kinetic model; repeat for the entries of any of the models given.")
    reference = df.BooleanFilter(
        field_name="provider_record", lookup_expr="isnull", exclude=True,
        help_text="true: polynomials fitted to reference records (/api/thermo-record/); false: the "
                  "entries of the kinetic models.")

    class Meta:
        model = dm.Thermo
        fields = {"id": ["in"], "species": ["exact", "in"]}
