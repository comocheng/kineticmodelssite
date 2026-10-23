"""
ChemKED Database Filters

Django-filter classes for filtering experimental datasets and datapoints.
"""

import django_filters
from django.db.models import Q, Count

from .models import (
    ExperimentDataset,
    ExperimentDatapoint,
    ExperimentType,
    ApparatusKind,
    CompositionKind,
    Apparatus,
)


def get_experiment_type_choices():
    """Get experiment types that actually exist in the database."""
    types = (
        ExperimentDataset.objects
        .exclude(experiment_type="")
        .order_by("experiment_type")
        .values_list("experiment_type", flat=True)
        .distinct()
    )
    choices = []
    type_labels = dict(ExperimentType.choices)
    for t in types:
        label = type_labels.get(t, t.title())
        choices.append((t, label))
    return choices


def get_apparatus_kind_choices():
    """Get apparatus kinds that actually exist in the database."""
    kinds = (
        Apparatus.objects
        .exclude(kind="")
        .values_list("kind", flat=True)
        .distinct()
    )
    choices = []
    kind_labels = dict(ApparatusKind.choices)
    for k in kinds:
        label = kind_labels.get(k, k.title())
        choices.append((k, label))
    return choices


def get_institution_choices():
    """Get institutions that actually exist in the database."""
    institutions = (
        Apparatus.objects
        .exclude(institution="")
        .values_list("institution", flat=True)
        .distinct()
        .order_by("institution")
    )
    return [(inst, inst) for inst in institutions]


class DatasetFilter(django_filters.FilterSet):
    """
    Filter for ChemKED datasets.
    """
    experiment_type = django_filters.ChoiceFilter(
        choices=[],  # Populated dynamically in __init__
        empty_label="All types",
    )

    apparatus_kind = django_filters.ChoiceFilter(
        field_name="apparatus__kind",
        choices=[],  # Populated dynamically in __init__
        empty_label="All apparatus",
    )

    reference_year_min = django_filters.NumberFilter(
        field_name="reference_year",
        lookup_expr="gte",
        label="Year (from)",
    )

    reference_year_max = django_filters.NumberFilter(
        field_name="reference_year",
        lookup_expr="lte",
        label="Year (to)",
    )

    reference_doi = django_filters.CharFilter(
        lookup_expr="icontains",
        label="DOI contains",
    )

    reference_journal = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Journal contains",
    )

    species = django_filters.CharFilter(
        method="filter_by_species",
        label="Species name",
    )

    institution = django_filters.ChoiceFilter(
        field_name="apparatus__institution",
        choices=[],  # Populated dynamically in __init__
        empty_label="All institutions",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate dynamic choices
        self.filters["experiment_type"].extra["choices"] = get_experiment_type_choices()
        self.filters["apparatus_kind"].extra["choices"] = get_apparatus_kind_choices()
        self.filters["institution"].extra["choices"] = get_institution_choices()

        # Update form field choices
        self.form.fields["experiment_type"].choices = [("", "All types")] + get_experiment_type_choices()
        self.form.fields["apparatus_kind"].choices = [("", "All apparatus")] + get_apparatus_kind_choices()
        self.form.fields["institution"].choices = [("", "All institutions")] + get_institution_choices()

        # Widget styling
        self.form.fields["experiment_type"].widget.attrs.update({
            "class": "form-select form-select-sm filter-auto-submit",
        })
        self.form.fields["apparatus_kind"].widget.attrs.update({
            "class": "form-select form-select-sm filter-auto-submit",
        })
        self.form.fields["institution"].widget.attrs.update({
            "class": "form-select form-select-sm filter-auto-submit",
        })
        self.form.fields["reference_year_min"].widget.attrs.update({
            "class": "form-control form-control-sm filter-auto-submit",
            "placeholder": "From",
            "min": "1900",
            "max": "2100",
        })
        self.form.fields["reference_year_max"].widget.attrs.update({
            "class": "form-control form-control-sm filter-auto-submit",
            "placeholder": "To",
            "min": "1900",
            "max": "2100",
        })
        self.form.fields["species"].widget.attrs.update({
            "class": "form-control form-control-sm filter-auto-submit",
            "placeholder": "e.g., CH4, n-heptane",
        })
        self.form.fields["reference_doi"].widget.attrs.update({
            "class": "form-control form-control-sm filter-auto-submit",
            "placeholder": "10.1016/...",
        })

    def filter_by_species(self, queryset, name, value):
        """Filter datasets containing a specific species."""
        if not value:
            return queryset
        return queryset.filter(
            Q(common_properties__composition__species__species_name__icontains=value) |
            Q(datapoints__composition__species__species_name__icontains=value)
        ).distinct()

    class Meta:
        model = ExperimentDataset
        fields = [
            "experiment_type",
            "apparatus_kind",
            "reference_year_min",
            "reference_year_max",
            "reference_doi",
            "reference_journal",
            "species",
            "institution",
        ]


class DatapointFilter(django_filters.FilterSet):
    """
    Filter for individual datapoints.
    """
    temperature_min = django_filters.NumberFilter(
        field_name="temperature",
        lookup_expr="gte",
        label="Temperature min (K)",
    )

    temperature_max = django_filters.NumberFilter(
        field_name="temperature",
        lookup_expr="lte",
        label="Temperature max (K)",
    )

    pressure_min = django_filters.NumberFilter(
        field_name="pressure",
        lookup_expr="gte",
        label="Pressure min (Pa)",
    )

    pressure_max = django_filters.NumberFilter(
        field_name="pressure",
        lookup_expr="lte",
        label="Pressure max (Pa)",
    )

    equivalence_ratio_min = django_filters.NumberFilter(
        field_name="equivalence_ratio",
        lookup_expr="gte",
        label="Equivalence ratio min",
    )

    equivalence_ratio_max = django_filters.NumberFilter(
        field_name="equivalence_ratio",
        lookup_expr="lte",
        label="Equivalence ratio max",
    )

    experiment_type = django_filters.ChoiceFilter(
        field_name="dataset__experiment_type",
        choices=ExperimentType.choices,
        empty_label="All experiment types",
    )

    species = django_filters.CharFilter(
        method="filter_by_species",
        label="Species name",
    )

    def filter_by_species(self, queryset, name, value):
        """Filter datapoints containing a specific species."""
        if not value:
            return queryset
        return queryset.filter(
            Q(composition__species__species_name__icontains=value) |
            Q(dataset__common_properties__composition__species__species_name__icontains=value)
        ).distinct()

    class Meta:
        model = ExperimentDatapoint
        fields = [
            "temperature_min",
            "temperature_max",
            "pressure_min",
            "pressure_max",
            "equivalence_ratio_min",
            "equivalence_ratio_max",
            "experiment_type",
            "species",
        ]
