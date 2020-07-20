from database.models.kinetic_data import BaseKineticsData
from itertools import zip_longest

from django.urls import reverse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views import View
from django.views.generic import TemplateView, DetailView
from django_filters.views import FilterView
from django.http import HttpResponse
from rmgpy.molecule.draw import MoleculeDrawer

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
from .filters import SpeciesFilter, ReactionFilter, SourceFilter


class BaseView(TemplateView):
    template_name = "database/base.html"


class IndexView(TemplateView):
    template_name = "index.html"





class SpeciesFilterView(FilterView):
    filterset_class = SpeciesFilter
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        super_response = super().get(request, *args, **kwargs)
        pk = request.GET.get("pk")
        try:
            Species.objects.get(pk=pk)
            return HttpResponseRedirect(reverse("species-detail", args=[pk]))
        except Species.DoesNotExist as e:
            return super_response


class SourceFilterView(FilterView):
    filterset_class = SourceFilter
    paginate_by = 25


class ReactionFilterView(FilterView):
    filterset_class = ReactionFilter
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        super_response = super().get(request, *args, **kwargs)
        pk = request.GET.get("pk")
        if pk is not None:
            return HttpResponseRedirect(reverse("reaction-detail", args=[pk]))
        else:
            return super_response


class SpeciesDetail(DetailView):
    model = Species

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        species = self.get_object()
        structures = Structure.objects.filter(isomer__species=species)
        context["names"] = set(species.speciesname_set.all().values_list("name", flat=True))
        context["adjlists"] = structures.values_list("adjacency_list", flat=True)
        context["smiles"] = structures.values_list("smiles", flat=True)
        context["isomer_inchis"] = species.isomer_set.values_list("inchi", flat=True)
        context["thermo_list"] = Thermo.objects.filter(species=species)
        context["transport_list"] = Transport.objects.filter(species=species)
        context["structures"] = structures

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

        try:
            reactants = reaction.stoich_reactants()
            products = reaction.stoich_products()
        except NotImplementedError:
            reactants = reaction.reactants()
            products = reaction.products()

        context["reactants"] = reactants
        context["products"] = products
        context["kinetics_data"] = [
            (k, BaseKineticsData.objects.get_subclass(kinetics=k))
            for k in reaction.kinetics_set.all()
        ]

        return context


class KineticModelDetail(DetailView):
    model = KineticModel
    context_object_name = "kinetic_model"
    paginate_per_page = 25

    def get_context_data(self, **kwargs):
        kinetic_model = self.get_object()
        context = super().get_context_data(**kwargs)
        thermo = kinetic_model.thermo.order_by("species")
        transport = kinetic_model.transport.order_by("species")
        thermo_transport = list(zip_longest(thermo, transport))
        kinetics = kinetic_model.kinetics.order_by("reaction")

        paginator1 = Paginator(thermo_transport, self.paginate_per_page)
        page1 = self.request.GET.get("page1", 1)
        try:
            paginated_thermo_transport = paginator1.page(page1)
        except PageNotAnInteger:
            paginated_thermo_transport = paginator1.page(1)
        except EmptyPage:
            paginated_thermo_transport = paginator1.page(paginator1.num_pages)

        paginator2 = Paginator(kinetics, self.paginate_per_page)
        page2 = self.request.GET.get("page2", 1)
        try:
            paginated_kinetics = paginator2.page(page2)
        except PageNotAnInteger:
            paginated_kinetics = paginator2.page(1)
        except EmptyPage:
            paginated_kinetics = paginator2.page(paginator2.num_pages)

        context["thermo_transport"] = paginated_thermo_transport
        context["kinetics"] = paginated_kinetics
        context["page1"] = page1
        context["page2"] = page2
        context["source"] = kinetic_model.source

        return context


class KineticsDetail(DetailView):
    model = Kinetics
    context_object_name = "kinetics"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kinetics = self.get_object()
        context["table_data"] = BaseKineticsData.objects.get_subclass(
            kinetics=kinetics
        ).table_data()
        context["efficiencies"] = kinetics.data.efficiency_set.all()

        return context


class DrawStructure(View):
    def get(self, request, pk):
        structure = Structure.objects.get(pk=pk)
        molecule = structure.to_rmg()
        surface, _, _, = MoleculeDrawer().draw(molecule, file_format="png")
        response = HttpResponse(surface.write_to_png(), content_type="image/png")

        return response
