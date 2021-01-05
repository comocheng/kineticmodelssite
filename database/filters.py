import django_filters
from dal import autocomplete
from django.db.models import Count

from database import models


class SpeciesFilter(django_filters.FilterSet):
    speciesname__name = django_filters.CharFilter(
        field_name="speciesname",
        lookup_expr="name",
        distinct=True,
        label="Species Name",
    )
    isomers = django_filters.ModelMultipleChoiceFilter(
        field_name="isomers",
        queryset=models.Isomer.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url="isomer-autocomplete",
            attrs={"data-html": True},
        ),
    )
    isomers__structures = django_filters.ModelMultipleChoiceFilter(
        label="Structures",
        field_name="isomers",
        lookup_expr="structure",
        queryset=models.Structure.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url="structure-autocomplete",
            attrs={"data-html": True},
        ),
    )

    class Meta:
        model = models.Species
        fields = ["prime_id", "cas_number"]


class ReactionFilter(django_filters.FilterSet):
    reactant1 = django_filters.ModelChoiceFilter(
        queryset=models.Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_reactant",
        label="Reactant",
        widget=autocomplete.ModelSelect2(
            url="species-autocomplete",
            attrs={"data-html": True},
        ),
    )
    reactant2 = django_filters.ModelChoiceFilter(
        queryset=models.Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_reactant",
        label="Reactant",
        widget=autocomplete.ModelSelect2(
            url="species-autocomplete",
            attrs={"data-html": True},
        ),
    )
    product1 = django_filters.ModelChoiceFilter(
        queryset=models.Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_product",
        label="Product",
        widget=autocomplete.ModelSelect2(
            url="species-autocomplete",
            attrs={"data-html": True},
        ),
    )
    product2 = django_filters.ModelChoiceFilter(
        queryset=models.Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_product",
        label="Product",
        widget=autocomplete.ModelSelect2(
            url="species-autocomplete",
            attrs={"data-html": True},
        ),
    )

    def filter_reactant(self, queryset, name, value):
        return queryset.filter(**{name: value}, stoichiometry__coeff__lt=0)

    def filter_product(self, queryset, name, value):
        return queryset.filter(**{name: value}, stoichiometry__coeff__gt=0)

    class Meta:
        model = models.Reaction
        fields = (
            "prime_id",
            "reversible",
        )


class SourceFilter(django_filters.FilterSet):
    class Meta:
        model = models.Source
        fields = ["prime_id", "publication_year", "source_title", "journal_name", "doi"]
