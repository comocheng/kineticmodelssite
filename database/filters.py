import django_filters

from .models import Species, Reaction, Source


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
    isomer__structure__electronic_state = django_filters.NumberFilter(
        field_name="isomer",
        lookup_expr="structure__electronic_state",
        label="Structure Electronic State",
    )

    class Meta:
        model = Species
        fields = ["prime_id", "formula", "inchi", "cas_number"]


class ReactionFilter(django_filters.FilterSet):
    species__name = django_filters.CharFilter(
        field_name="species", lookup_expr="speciesname__name", distinct=True, label="Species Name"
    )

    class Meta:
        model = Reaction
        fields = ["prime_id", "reversible"]


class SourceFilter(django_filters.FilterSet):
    class Meta:
        model = Source
        fields = ["prime_id", "publication_year", "source_title", "journal_name", "doi"]
