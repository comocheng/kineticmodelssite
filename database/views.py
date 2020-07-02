import django_filters
from django.views.generic import TemplateView, DetailView

from .models import (
    Species,
    Structure,
    KineticModel,
    Thermo,
    Transport,
    Source,
    Reaction,
    Kinetics,
)


class BaseView(TemplateView):
    template_name = "database/base.html"


class IndexView(TemplateView):
    template_name = "index.html"


class SpeciesFilter(django_filters.FilterSet):
    speciesname__name = django_filters.CharFilter(
        field_name="speciesname", lookup_expr="name", label="Species Name"
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


class SourceFilter(django_filters.FilterSet):
    sourcename_name = django_filters.CharFilter(
        field_name="sourcename", lookup_expr="name", label="Source Name"
    )

    class Meta:
        model = Source
        fields = ["name", "prime_id", "publication_year", "source_title", "doi"]


class ReactionFilter(django_filters.FilterSet):
    class Meta:
        model = Reaction
        fields = ["species", "prime_id", "reversible"]


class SpeciesDetail(DetailView):
    model = Species

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        structures = Structure.objects.filter(isomer__species=self.get_object())
        context["names"] = set(
            self.get_object().speciesname_set.all().values_list("name", flat=True)
        )
        context["adjlists"] = structures.values_list("adjacency_list", flat=True)
        context["smiles"] = structures.values_list("smiles", flat=True)
        context["isomer_inchis"] = self.get_object().isomer_set.values_list("inchi", flat=True)
        context["thermo_list"] = Thermo.objects.filter(species=self.get_object())
        context["transport_list"] = Transport.objects.filter(species=self.get_object())

        return context


class ThermoDetail(DetailView):
    model = Thermo
    context_object_name = "thermo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thermo = self.get_object()
        kinetic_model = KineticModel.objects.get(thermo=thermo)
        context["species_name"] = kinetic_model.speciesname_set.get(species=thermo.species).name
        context["species"] = thermo.species
        context["source"] = thermo.source
        context["species_name"] = kinetic_model.speciesname_set.get(species=thermo.species).name
        return context


class TransportDetail(DetailView):
    model = Transport

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transport = self.get_object()
        kinetic_model = KineticModel.objects.get(transport=transport)
        context["species_name"] = kinetic_model.speciesname_set.get(species=transport.species).name

        return context


class SourceDetail(DetailView):
    model = Source

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        kinetic_models = source.kineticmodel_set.all()
        context["source"] = source
        context["kinetic_models"] = kinetic_models
        return context


class ReactionDetail(DetailView):
    model = Reaction
    context_object_name = "reaction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reaction = self.get_object()
        context["reactants"] = reaction.reactants()
        context["products"] = reaction.products()
        context["kinetics"] = reaction.kinetics_set.all()

        return context


class KineticsDetail(DetailView):
    model = Kinetics
    context_object_name = "kinetics"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kinetics = self.get_object()
        kineticdata = None
        kin_type = None

        for kt in [
            "arrhenius",
            "arrheniusep",
            "chebyshev",
            "lindemann",
            "multiarrhenius",
            "multipdeparrhenius",
            "pdeparrhenius",
            "thirdbody",
            "troe",
        ]:
            try:
                kineticdata = getattr(kinetics.basekineticsdata, kt)
                kin_type = kt
                break
            except AttributeError:
                continue

        context["kin_type"] = kin_type
        context["kineticdata"] = kineticdata

        return context
