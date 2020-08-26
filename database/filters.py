import django_filters
from django.db.models import Count

from .models import Species, Reaction, Source, Stoichiometry


class SpeciesFilter(django_filters.FilterSet):
    speciesname__name = django_filters.CharFilter(
        field_name="speciesname", lookup_expr="name", distinct=True, label="Species Name",
    )
    isomer__inchi = django_filters.CharFilter(
        field_name="isomer", lookup_expr="inchi", label="Isomer InChI"
    )
    isomer__structure__smiles = django_filters.CharFilter(
        field_name="isomer", lookup_expr="structure__smiles", label="Structure SMILES"
    )
    isomer__structure__adjacency_list = django_filters.CharFilter(
        field_name="isomer",
        lookup_expr="structure__adjacency_list",
        label="Structure Adjacency List",
    )
    isomer__structure__multiplicity = django_filters.NumberFilter(
        field_name="isomer", lookup_expr="structure__multiplicity", label="Structure Multiplicity",
    )

    class Meta:
        model = Species
        fields = ["prime_id", "formula", "inchi", "cas_number"]


class ReactionFilter(django_filters.FilterSet):
    reactant1 = django_filters.ModelChoiceFilter(
        queryset=Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_reactant",
        label="Reactant",
    )
    reactant2 = django_filters.ModelChoiceFilter(
        queryset=Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_reactant",
        label="Reactant",
    )
    product1 = django_filters.ModelChoiceFilter(
        queryset=Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_product",
        label="Product",
    )
    product2 = django_filters.ModelChoiceFilter(
        queryset=Species.objects.annotate(reaction_count=Count("reaction")).filter(
            reaction_count__gt=0
        ),
        field_name="species",
        method="filter_product",
        label="Product",
    )

    def filter_reactant(self, queryset, name, value):
        reaction_ids = Stoichiometry.objects.filter(
            **{name: value}, stoichiometry__lt=0
        ).values_list("reaction", flat=True)

        return Reaction.objects.filter(id__in=reaction_ids)

    def filter_product(self, queryset, name, value):
        reaction_ids = Stoichiometry.objects.filter(
            **{name: value}, stoichiometry__gt=0
        ).values_list("reaction", flat=True)

        return Reaction.objects.filter(id__in=reaction_ids)

    class Meta:
        model = Reaction
        fields = (
            "prime_id",
            "reversible",
        )


class SourceFilter(django_filters.FilterSet):
    class Meta:
        model = Source
        fields = ["prime_id", "publication_year", "source_title", "journal_name", "doi"]
