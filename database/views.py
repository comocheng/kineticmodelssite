import functools
from itertools import zip_longest
from collections import defaultdict
from datetime import datetime

from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views import View
from django.views.generic import TemplateView, DetailView
from django.views.generic.edit import FormView, CreateView
from django_filters.views import FilterView
from django.http import HttpResponse
from rmgpy.molecule.draw import MoleculeDrawer

from .models import (
    BaseKineticsData,
    Species,
    Structure,
    KineticModel,
    Thermo,
    Transport,
    Source,
    Reaction,
    Kinetics,
    SpeciesRevision
)
from .filters import SpeciesFilter, ReactionFilter, SourceFilter
from .forms import RegistrationForm, StoichiometryFormSet


class SidebarLookup:

    def __init__(self, cls, *args, **kwargs):
        cls.get = self.lookup_get(cls.get)
        cls.get_context_data = self.lookup_get_context_data(cls.get_context_data)
        self.cls = cls

    def as_view(self, *args, **kwargs):
        return self.cls.as_view(*args, **kwargs)

    def lookup_get(self, func):
        @functools.wraps(func)
        def inner(self, request, *args, **kwargs):
            species_pk = request.GET.get("species_pk")
            reaction_pk = request.GET.get("reaction_pk")
            source_pk = request.GET.get("source_pk")
            if species_pk:
                try:
                    Species.objects.get(pk=species_pk)
                    return HttpResponseRedirect(reverse("species-detail", args=[species_pk]))
                except Species.DoesNotExist:
                    response = func(self, request, *args, **kwargs)
                    return response
            elif reaction_pk:
                try:
                    Reaction.objects.get(pk=reaction_pk)
                    return HttpResponseRedirect(reverse("reaction-detail", args=[reaction_pk]))
                except Reaction.DoesNotExist:
                    return func(self, request, *args, **kwargs)
            elif source_pk:
                try:
                    Source.objects.get(pk=source_pk)
                    return HttpResponseRedirect(reverse("source-detail", args=[source_pk]))
                except Source.DoesNotExist:
                    return func(self, request, *args, **kwargs)
            else:
                return func(self, request, *args, **kwargs)

        return inner

    def lookup_get_context_data(self, func):
        @functools.wraps(func)
        def inner(self, *args, **kwargs):
            context = func(self, *args, **kwargs)
            species_pk = self.request.GET.get("species_pk")
            reaction_pk = self.request.GET.get("reaction_pk")
            source_pk = self.request.GET.get("source_pk")
            species_invalid = "Species with that ID wasn't found"
            reaction_invalid = "Reaction with that ID wasn't found"
            source_invalid = "Source with that ID wasn't found"
            if species_pk:
                try:
                    Species.objects.get(pk=species_pk)
                except Species.DoesNotExist:
                    context["species_invalid"] = species_invalid
                    return context
            if reaction_pk:
                try:
                    Reaction.objects.get(pk=reaction_pk)
                    return context
                except Reaction.DoesNotExist:
                    context["reaction_invalid"] = reaction_invalid
                    return context
            if source_pk:
                try:
                    Source.objects.get(pk=source_pk)
                    return context
                except Source.DoesNotExist:
                    context["source_invalid"] = source_invalid
                    return context
            else:
                return context

        return inner


@SidebarLookup
class BaseView(TemplateView):
    template_name = "database/base.html"


@SidebarLookup
class SpeciesFilterView(FilterView):
    filterset_class = SpeciesFilter
    paginate_by = 25
    queryset = Species.objects.order_by("id")


@SidebarLookup
class SourceFilterView(FilterView):
    filterset_class = SourceFilter
    paginate_by = 25


@SidebarLookup
class ReactionFilterView(FilterView):
    filterset_class = ReactionFilter
    paginate_by = 25


@SidebarLookup
class SpeciesDetail(DetailView):
    model = Species
    paginate_per_page = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        species = self.get_object()
        structures = Structure.objects.filter(isomer__species=species)
        reactions = Reaction.objects.filter(species=species).order_by("id")
        thermos = Thermo.objects.filter(species=species)

        names_models = defaultdict(list)
        for values in species.speciesname_set.values(
            "name", "kinetic_model__model_name", "kinetic_model"
        ):
            name, model_name, model_id = values.values()
            if name:
                names_models[name].append((model_name, model_id))

        context["names_models"] = sorted(list(names_models.items()), key=lambda x: -len(x[1]))
        context["adjlists"] = structures.values_list("adjacency_list", flat=True)
        context["smiles"] = structures.values_list("smiles", flat=True)
        context["isomer_inchis"] = species.isomers.values_list("inchi", flat=True)
        context["thermos_models"] = [(thermo, thermo.kineticmodel_set.all()) for thermo in thermos]
        context["transport_list"] = Transport.objects.filter(species=species)
        context["structures"] = structures

        paginator = Paginator(reactions, self.paginate_per_page)
        page = self.request.GET.get("page", 1)
        try:
            paginated_reactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_reactions = paginator.page(1)
        except EmptyPage:
            paginated_reactions = paginator.page(paginator.num_pages)

        context["reactions"] = paginated_reactions
        context["page"] = page

        return context


@SidebarLookup
class ThermoDetail(DetailView):
    model = Thermo
    context_object_name = "thermo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thermo = self.get_object()
        thermo_comments = thermo.thermocomment_set.all()
        context["thermo_comments"] = thermo_comments
        return context


@SidebarLookup
class TransportDetail(DetailView):
    model = Transport

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transport = self.get_object()
        kinetic_model = KineticModel.objects.get(transport=transport)
        context["species_name"] = kinetic_model.speciesname_set.get(species=transport.species).name

        return context


@SidebarLookup
class SourceDetail(DetailView):
    model = Source

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        kinetic_models = source.kineticmodel_set.all()
        context["source"] = source
        context["kinetic_models"] = kinetic_models
        return context


@SidebarLookup
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
        context["kinetics_modelnames"] = [
            (k, k.kineticmodel_set.values_list("model_name", flat=True))
            for k in reaction.kinetics_set.all()
        ]

        return context


@SidebarLookup
class KineticModelDetail(DetailView):
    model = KineticModel
    context_object_name = "kinetic_model"
    paginate_per_page = 25

    def get_context_data(self, **kwargs):
        kinetic_model = self.get_object()
        context = super().get_context_data(**kwargs)
        thermo = kinetic_model.thermocomment_set.order_by("thermo__species__id")
        transport = kinetic_model.transportcomment_set.order_by("transport__species__id")
        thermo_transport = list(zip_longest(thermo, transport))
        kinetics_data = kinetic_model.kineticscomment_set.order_by("kinetics__reaction__id")

        paginator1 = Paginator(thermo_transport, self.paginate_per_page)
        page1 = self.request.GET.get("page1", 1)
        try:
            paginated_thermo_transport = paginator1.page(page1)
        except PageNotAnInteger:
            paginated_thermo_transport = paginator1.page(1)
        except EmptyPage:
            paginated_thermo_transport = paginator1.page(paginator1.num_pages)

        paginator2 = Paginator(kinetics_data, self.paginate_per_page)
        page2 = self.request.GET.get("page2", 1)
        try:
            paginated_kinetics_data = paginator2.page(page2)
        except PageNotAnInteger:
            paginated_kinetics_data = paginator2.page(1)
        except EmptyPage:
            paginated_kinetics_data = paginator2.page(paginator2.num_pages)

        context["thermo_transport"] = paginated_thermo_transport
        context["kinetics_data"] = paginated_kinetics_data
        context["page1"] = page1
        context["page2"] = page2
        context["source"] = kinetic_model.source

        return context


@SidebarLookup
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
        (
            surface,
            _,
            _,
        ) = MoleculeDrawer().draw(molecule, file_format="png")
        response = HttpResponse(surface.write_to_png(), content_type="image/png")

        return response


class RegistrationView(FormView):
    template_name = "database/register.html"
    form_class = RegistrationForm
    success_url = "/"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)

        return super().form_valid(form)


class RevisionView(LoginRequiredMixin, CreateView):
    template_name = "database/revision.html"
    login_url = "login/"

    def get_success_url(self):
        return reverse(self.url_name, args=[self.get_object().pk])

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get("pk"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context["object"] = obj
        context["name"] = obj.__class__.__name__

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()

        return kwargs

    def save_form(self, form):
        self.object = form.save(commit=False)
        self.object.id = None
        self.object.revision = True
        self.object.created_by = self.request.user
        self.object.created_on = datetime.now()
        self.object.target = self.get_object()
        self.object.status = self.object.PENDING
        self.object.save()
        form.save_m2m()

        return self.object


    def form_valid(self, form):
        self.save_form(form)

        return HttpResponseRedirect(self.get_success_url())


class SpeciesRevisionView(RevisionView):
    model = Species
    url_name = "species-detail"
    fields = ["prime_id", "cas_number", "isomers"]


class ReactionRevisionView(RevisionView):
    model = Reaction
    url_name = "reaction-detail"
    fields = ["prime_id", "reversible"]
    formset_class = StoichiometryFormSet

    def get_formset(self):
        instance = self.get_object()
        if self.request.POST:
            return self.formset_class(self.request.POST, instance=instance)
        else:
            return self.formset_class(instance=instance)

    def post(self, request):
        form = self.get_form()
        formset = self.get_formset()
        self.object = self.get_object()

        if form.is_valid() and formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        instance = self.save_form(form)
        formset = self.get_formset()
        objects = formset.save(commit=False)
        for o in objects:
            o.id = None
            o.revision = True
            o.created_by = self.request.user
            o.created_on = datetime.now()
            o.reaction = instance
            o.save()

        return HttpResponseRedirect(self.get_success_url())


class RevisionApprovalView(UserPassesTestMixin, View):

    def test_func(self):
        return self.request.user.is_staff

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get("pk"))

    def post(self, request, pk):
        revision = self.get_object()
        self.update_model(revision)
        revision.status = revision.APPROVED
        revision.save()

        return HttpResponseRedirect(self.get_url())


class SpeciesRevisionApprovalView(RevisionApprovalView):
    model = SpeciesRevision

    def get_url(self):
        return reverse("admin:database_speciesrevision_changelist")

    def update_model(self, revision):
        species = revision.target
        species.prime_id = revision.prime_id
        species.cas_number = revision.cas_number
        species.isomers.clear()
        species.isomers.add(*revision.isomers.all())
        species.save()
