import functools
from itertools import zip_longest
from collections import defaultdict

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth import login
from kms.access import SiteLoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Count, Prefetch, Q
from django.views import View
from django.views.generic import TemplateView, DetailView, ListView
from django.views.generic.edit import FormView, CreateView, UpdateView, DeleteView
from django_filters.views import FilterView
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.html import format_html
from rmgpy.molecule.draw import MoleculeDrawer

from database import models
from database.services import chemistry_index, curves, rmg_matching, shared_chemistry, sub_mechanisms
from database.services.chemical_identity import rates_match
from .models import (
    Species,
    Structure,
    KineticModel,
    Thermo,
    Transport,
    Source,
    Reaction,
    Kinetics,
    Author,
    Authorship,
)
from .filters import SpeciesFilter, ReactionFilter, SourceFilter
from .forms import RegistrationForm, SourceForm, AuthorshipFormSet, KineticModelForm, AuthorForm
from database.templatetags import renders
from database.services import exports
from provenance import resolver


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
    template_name = "database/home.html"
    # Get counts for display on home page
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["species_count"] = Species.objects.count()
        context["model_count"] = KineticModel.objects.count()
        context["reaction_count"] = Reaction.objects.count()
        context["source_count"] = Source.objects.count()
        return context

class KineticModelFilterView(ListView):
    model = KineticModel
    paginate_by = 25
    queryset = KineticModel.objects.order_by("id")
    template_name = "database/kineticmodel_filter.html"

@SidebarLookup
class SpeciesFilterView(FilterView):
    filterset_class = SpeciesFilter
    paginate_by = 25
    queryset = Species.objects.order_by("id").prefetch_related(
        Prefetch("isomers", queryset=models.Isomer.objects.select_related("formula").prefetch_related(
            Prefetch("structure_set", queryset=Structure.objects.order_by("pk"))
        )),
        "speciesname_set",
        Prefetch("thermo_set", queryset=Thermo.objects.order_by("pk")),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Build result summaries from page-sized prefetches, avoiding per-row queries.
        for species in context["object_list"]:
            isomers = list(species.isomers.all())
            structures = [s for isomer in isomers for s in isomer.structure_set.all()]
            species.search_formula = isomers[0].formula.formula if isomers else ""
            species.search_structure = structures[0] if structures else None
            species.search_pubchem_cids = sorted({s.pubchem_cid for s in structures if s.pubchem_cid})
            iupac_names = sorted({s.iupac_name for s in structures if s.iupac_name})
            model_names = sorted({n.name for n in species.speciesname_set.all() if n.name})
            species.search_names = iupac_names + [n for n in model_names if n not in iupac_names]
            thermo = next(iter(species.thermo_set.all()), None)
            species.search_enthalpy = None
            if thermo:
                try:
                    species.search_enthalpy = f"{thermo.enthalpy298:,.0f}"
                except (ValueError, TypeError):
                    pass
        context["legacy_filters"] = any(self.request.GET.get(key) for key in (
            "prime_id", "cas_number", "speciesname__name", "isomers", "isomers__structures"
        ))
        return context


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
        structures = Structure.objects.filter(isomer__species=species).select_related("isomer")
        reactions = Reaction.objects.filter(species=species).order_by("id")

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
        context["thermo_list"] = Thermo.objects.filter(species=species)
        # Include records matched through a resonance form drawn under another isomer,
        # and the ATcT-constrained thermo derived from any of them.
        shown = models.ThermoRecord.objects.filter(
            Q(structure__isomer__in=species.isomers.all())
            | Q(thermoenrichmentjob__structure__isomer__in=species.isomers.all())
        ).values("pk")
        context["thermo_records"] = models.ThermoRecord.objects.filter(
            Q(pk__in=shown) | Q(enthalpy_source__in=shown)
        ).distinct().select_related("structure", "nasa_thermo", "enthalpy_source", "heat_capacity_source")
        context["thermo_plot"] = curves.species_thermo_plot(
            Thermo.objects.filter(species=species, provider_record__isnull=True)
            .prefetch_related("thermocomment_set__kinetic_model"),
            context["thermo_records"])
        sidebar_thermo = species.thermo_set.select_related("provider_record").order_by("pk").first()
        if sidebar_thermo:
            try:
                context["sidebar_enthalpy"] = f"{sidebar_thermo.enthalpy298:,.0f}"
                context["sidebar_thermo"] = sidebar_thermo
                if hasattr(sidebar_thermo, "provider_record"):
                    context["sidebar_thermo_source"] = sidebar_thermo.provider_record.get_provider_display()
                else:
                    # Name the models that supplied this entry, first importer first.
                    model_names = list(dict.fromkeys(sidebar_thermo.thermocomment_set.order_by("pk")
                                                     .values_list("kinetic_model__model_name", flat=True)))
                    context["sidebar_thermo_models"] = ", ".join(model_names)
                    context["sidebar_thermo_source"] = (
                        model_names[0] + (f" + {len(model_names) - 1} more" if len(model_names) > 1 else "")
                        if model_names else "Imported model thermo")
            except (ValueError, TypeError):
                pass
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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        rdf = resolver.negotiate_record(request, "thermo", self.object)
        if rdf is not None:
            return rdf
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thermo = self.get_object()
        thermo_comments = thermo.thermocomment_set.all()
        context["thermo_comments"] = thermo_comments
        context["thermo_plot"] = curves.single_thermo_plot(thermo, f"Thermo {thermo.pk}")
        return context


@SidebarLookup
class TransportDetail(DetailView):
    model = Transport

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        rdf = resolver.negotiate_record(request, "transport", self.object)
        if rdf is not None:
            return rdf
        return self.render_to_response(self.get_context_data(object=self.object))

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

        context["reactants"] = reaction.reactants()
        context["products"] = reaction.products()
        context["kinetics_modelnames"] = [
            (k, k.kineticmodel_set.order_by("model_name").only("pk", "model_name"))
            for k in reaction.kinetics_set.all()
        ]
        context["rate_plot"] = curves.reaction_rate_plot(reaction)
        records = []
        if reaction.canonical_key:
            model_rates = [(k.rate_fingerprint, list(rows)) for k, rows in context["kinetics_modelnames"]]
            for record in models.KineticsRecord.objects.filter(
                    reaction__canonical_key=reaction.canonical_key).order_by("provider", "library"):
                same = record.canonical_direction == reaction.canonical_direction
                identical = sorted({m for fingerprint, rows in model_rates
                                    if same and rates_match(fingerprint, record.rate_fingerprint) for m in rows},
                                   key=lambda m: m.model_name)
                records.append({"record": record, "same_direction": same, "identical_models": identical,
                                "entry_url": rmg_matching.entry_url(record)})
        context["rmg_records"] = records
        context["rmg_family"] = reaction.rmg_family
        context["reverse_reactions"] = (
            Reaction.objects.filter(canonical_key=reaction.canonical_key).exclude(pk=reaction.pk).order_by("pk")
            if reaction.canonical_key else Reaction.objects.none())

        return context


@SidebarLookup
class KineticModelDetail(DetailView):
    model = KineticModel
    context_object_name = "kinetic_model"
    paginate_per_page = 25

    def get_context_data(self, **kwargs):
        kinetic_model = self.get_object()
        context = super().get_context_data(**kwargs)
        
        # Get thermo and transport comments
        thermo_comments = kinetic_model.thermocomment_set.select_related('thermo__species')
        transport_comments = kinetic_model.transportcomment_set.select_related('transport__species')
        
        # Build dictionaries keyed by species ID for proper matching
        thermo_by_species = {tc.thermo.species_id: tc for tc in thermo_comments}
        transport_by_species = {tc.transport.species_id: tc for tc in transport_comments}
        
        # Get all unique species IDs from both thermo and transport
        all_species_ids = set(thermo_by_species.keys()) | set(transport_by_species.keys())
        
        # Create paired list: (thermo_comment, transport_comment) matched by species
        thermo_transport = []
        for species_id in sorted(all_species_ids):
            thermo_comment = thermo_by_species.get(species_id)
            transport_comment = transport_by_species.get(species_id)
            thermo_transport.append((thermo_comment, transport_comment))
        
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
        context["library_overlaps"] = kinetic_model.library_overlaps.filter(identical__gt=0).order_by("-identical")[:10]
        context["related_models"] = (models.SharedChemistry.objects.filter(model_a=kinetic_model, layer="all")
                                     .select_related("model_b").order_by("-identical")[:10])
        earlier = shared_chemistry.lineage(kinetic_model)
        layer_rows = defaultdict(list)
        for row in models.SharedChemistry.objects.filter(model_a=kinetic_model).exclude(layer="all").select_related("model_b"):
            layer_rows[row.layer].append(row)
        variant_of = {v.sub_mechanism.layer: v for v in kinetic_model.sub_mechanism_variants.select_related("sub_mechanism")}
        context["layer_summary"] = [
            {"layer": layer, "reactions": rows[0].reactions, "closest": max(rows, key=lambda r: r.identical),
             "earlier": earlier.get(layer), "variant": variant_of.get(layer)}
            for layer, rows in sorted(layer_rows.items(), key=lambda item: -item[1][0].reactions)]
        # Count every model in each block, not just the one this page is filtered on.
        context["blocks"] = (models.ChemistryBlock.objects.filter(pk__in=kinetic_model.chemistry_blocks.values("pk"))
                             .select_related("origin").annotate(model_count=Count("kinetic_models")).order_by("-size")[:6])

        return context


class KineticModelDownloadView(View):
    def get(self, request, pk, format):
        kinetic_model = get_object_or_404(KineticModel, pk=pk)
        strict_value = request.GET.get("strict", "").strip().lower()
        strict = strict_value in {"1", "true", "yes", "on"}

        try:
            if format == "chemkin":
                result = exports.build_chemkin_bundle(kinetic_model, strict=strict)
            elif format in {"cantera", "cantera-yaml", "yaml"}:
                result = exports.build_cantera_yaml(kinetic_model, strict=strict)
            else:
                return HttpResponseBadRequest("Unknown download format.")
        except exports.ExportError as exc:
            return HttpResponseBadRequest(str(exc))

        response = HttpResponse(result.content, content_type=result.content_type)
        response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
        return response


@SidebarLookup
class KineticsDetail(DetailView):
    model = Kinetics
    context_object_name = "kinetics"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        rdf = resolver.negotiate_record(request, "kinetics", self.object)
        if rdf is not None:
            return rdf
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kinetics = self.get_object()
        context["table_data"] = kinetics.data.table_data() if hasattr(kinetics.data, "table_data") else []
        context["kinetics_comments"] = kinetics.kineticscomment_set.order_by("kinetic_model__id")
        context["rate_plot"] = curves.single_rate_plot(kinetics, f"Kinetics {kinetics.pk}")

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


class RegistrationView(SiteLoginRequiredMixin, FormView):
    template_name = "database/register.html"
    form_class = RegistrationForm
    success_url = "/"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)

        return super().form_valid(form)


class AutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = self.model.objects.all()

        if self.q:
            for query in self.queries:
                try:
                    filtered = queryset.filter(**{query: self.q})
                    if filtered:
                        return filtered
                except ValueError:
                    continue

        return queryset if not self.q else []


class SpeciesAutocompleteView(AutocompleteView):
    model = Species
    queries = [
        "speciesname__name__istartswith",
        "isomers__formula__formula",
        "prime_id",
        "cas_number",
        "id",
    ]

    def get_result_label(self, item):
        return renders.render_species_list_card(item)

    def get_selected_result_label(self, item):
        return str(item)


class IsomerAutocompleteView(AutocompleteView):
    model = models.Isomer
    queries = ["inchi__istartswith", "formula__formula__istartswith", "id"]


class StructureAutocompleteView(AutocompleteView):
    model = models.Structure
    queries = ["adjacency_list__istartswith", "smiles__istartswith", "multiplicity", "id"]

    def get_result_label(self, item):
        draw_url = reverse("draw-structure", args=[item.pk])
        return format_html(f'<img src="{draw_url}" />')


# =============================================================================
# Source CRUD Views
# =============================================================================

class SourceCreateView(SiteLoginRequiredMixin, CreateView):
    """Create a new Source (publication)."""
    model = Source
    form_class = SourceForm
    template_name = 'database/source_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['authorship_formset'] = AuthorshipFormSet(self.request.POST, instance=self.object)
        else:
            context['authorship_formset'] = AuthorshipFormSet(instance=self.object)
        context['form_title'] = 'Add New Source'
        context['submit_text'] = 'Create Source'
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        authorship_formset = context['authorship_formset']
        
        if authorship_formset.is_valid():
            self.object = form.save()
            authorship_formset.instance = self.object
            
            # Process authorships, creating new authors if needed
            for authorship_form in authorship_formset:
                if authorship_form.cleaned_data and not authorship_form.cleaned_data.get('DELETE'):
                    firstname = authorship_form.cleaned_data.get('author_firstname', '').strip()
                    lastname = authorship_form.cleaned_data.get('author_lastname', '').strip()
                    author = authorship_form.cleaned_data.get('author')
                    
                    # Create new author if names provided but no author selected
                    if firstname and lastname and not author:
                        author, _ = Author.objects.get_or_create(
                            firstname=firstname,
                            lastname=lastname
                        )
                        authorship_form.instance.author = author
            
            authorship_formset.save()
            messages.success(self.request, f'Source "{self.object.source_title}" created successfully.')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))
    
    def get_success_url(self):
        return reverse('source-detail', kwargs={'pk': self.object.pk})


class SourceUpdateView(SiteLoginRequiredMixin, UpdateView):
    """Update an existing Source."""
    model = Source
    form_class = SourceForm
    template_name = 'database/source_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['authorship_formset'] = AuthorshipFormSet(self.request.POST, instance=self.object)
        else:
            context['authorship_formset'] = AuthorshipFormSet(instance=self.object)
        context['form_title'] = 'Edit Source'
        context['submit_text'] = 'Save Changes'
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        authorship_formset = context['authorship_formset']
        
        if authorship_formset.is_valid():
            self.object = form.save()
            
            # Process authorships, creating new authors if needed
            for authorship_form in authorship_formset:
                if authorship_form.cleaned_data and not authorship_form.cleaned_data.get('DELETE'):
                    firstname = authorship_form.cleaned_data.get('author_firstname', '').strip()
                    lastname = authorship_form.cleaned_data.get('author_lastname', '').strip()
                    author = authorship_form.cleaned_data.get('author')
                    
                    if firstname and lastname and not author:
                        author, _ = Author.objects.get_or_create(
                            firstname=firstname,
                            lastname=lastname
                        )
                        authorship_form.instance.author = author
            
            authorship_formset.save()
            messages.success(self.request, f'Source "{self.object.source_title}" updated successfully.')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))
    
    def get_success_url(self):
        return reverse('source-detail', kwargs={'pk': self.object.pk})


class SourceDeleteView(SiteLoginRequiredMixin, DeleteView):
    """Delete a Source."""
    model = Source
    template_name = 'database/confirm_delete.html'
    success_url = reverse_lazy('source-search')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Source'
        context['object_name'] = self.object.source_title or f'Source #{self.object.pk}'
        context['cancel_url'] = reverse('source-detail', kwargs={'pk': self.object.pk})
        return context
    
    def delete(self, request, *args, **kwargs):
        source = self.get_object()
        title = source.source_title or f'Source #{source.pk}'
        messages.success(request, f'Source "{title}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


# =============================================================================
# KineticModel CRUD Views
# =============================================================================

class KineticModelCreateView(SiteLoginRequiredMixin, CreateView):
    """Create a new KineticModel."""
    model = KineticModel
    form_class = KineticModelForm
    template_name = 'database/kineticmodel_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Add New Kinetic Model'
        context['submit_text'] = 'Create Model'
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Kinetic Model "{self.object.model_name}" created successfully.')
        return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('kinetic-model-detail', kwargs={'pk': self.object.pk})


class KineticModelUpdateView(SiteLoginRequiredMixin, UpdateView):
    """Update an existing KineticModel."""
    model = KineticModel
    form_class = KineticModelForm
    template_name = 'database/kineticmodel_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Kinetic Model'
        context['submit_text'] = 'Save Changes'
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Kinetic Model "{self.object.model_name}" updated successfully.')
        return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('kinetic-model-detail', kwargs={'pk': self.object.pk})


class KineticModelDeleteView(SiteLoginRequiredMixin, DeleteView):
    """Delete a KineticModel."""
    model = KineticModel
    template_name = 'database/confirm_delete.html'
    success_url = reverse_lazy('kinetic-model-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Kinetic Model'
        context['object_name'] = self.object.model_name
        context['cancel_url'] = reverse('kinetic-model-detail', kwargs={'pk': self.object.pk})
        # Warning about related data
        context['warning'] = (
            f'This will also remove all {self.object.species.count()} species names, '
            f'{self.object.kinetics.count()} kinetics comments, '
            f'{self.object.thermo.count()} thermo comments, and '
            f'{self.object.transport.count()} transport comments associated with this model.'
        )
        return context
    
    def delete(self, request, *args, **kwargs):
        model = self.get_object()
        messages.success(request, f'Kinetic Model "{model.model_name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


# =============================================================================
# Author CRUD Views
# =============================================================================

class AuthorListView(ListView):
    """List all Authors with unique names and aggregated publication counts."""
    model = Author
    template_name = 'database/author_list.html'
    paginate_by = 50
    context_object_name = 'author_list'
    
    def get_queryset(self):
        from django.db.models import Count, Min
        # Get unique authors by firstname+lastname, with publication count and primary ID
        # Uses Min('id') to get a representative ID for each unique author name
        return (
            Author.objects
            .values('firstname', 'lastname')
            .annotate(
                author_id=Min('id'),
                publication_count=Count('authorship', distinct=True)
            )
            .order_by('lastname', 'firstname')
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add total unique authors count
        context['total_authors'] = self.get_queryset().count()
        return context


class AuthorCreateView(SiteLoginRequiredMixin, CreateView):
    """Create a new Author."""
    model = Author
    form_class = AuthorForm
    template_name = 'database/author_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Add New Author'
        context['submit_text'] = 'Create Author'
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Author "{self.object.name}" created successfully.')
        return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('author-list')


class AuthorUpdateView(SiteLoginRequiredMixin, UpdateView):
    """Update an existing Author."""
    model = Author
    form_class = AuthorForm
    template_name = 'database/author_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Author'
        context['submit_text'] = 'Save Changes'
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Author "{self.object.name}" updated successfully.')
        return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('author-list')


class AuthorDeleteView(SiteLoginRequiredMixin, DeleteView):
    """Delete an Author."""
    model = Author
    template_name = 'database/confirm_delete.html'
    success_url = reverse_lazy('author-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Author'
        context['object_name'] = self.object.name
        context['cancel_url'] = reverse('author-list')
        pub_count = self.object.authorship_set.count()
        if pub_count:
            context['warning'] = f'This author is associated with {pub_count} publication(s).'
        return context
    
    def delete(self, request, *args, **kwargs):
        author = self.get_object()
        messages.success(request, f'Author "{author.name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


class KineticModelCompare(TemplateView):
    """Two models side by side: per-layer overlap and the shared reactions whose rates differ."""
    template_name = "database/kineticmodel_compare.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_models"] = KineticModel.objects.order_by("model_name").only("pk", "model_name")
        a, b = self.request.GET.get("a"), self.request.GET.get("b")
        if a and b and a.isdigit() and b.isdigit():
            context["model_a"] = get_object_or_404(KineticModel, pk=a)
            context["model_b"] = get_object_or_404(KineticModel, pk=b)
            context.update(shared_chemistry.compare(context["model_a"], context["model_b"]))
        return context


class KineticModelSimilarity(TemplateView):
    """Heatmap of identical rates between every pair of models, per layer."""
    template_name = "database/kineticmodel_similarity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        layer = self.request.GET.get("layer", "all")
        context["layers"] = ["all", *sorted(set(models.SharedChemistry.objects.exclude(layer="all")
                                                 .values_list("layer", flat=True)))]
        context["layer"] = layer
        context["matrix"] = shared_chemistry.similarity_matrix(layer)
        context["top_pairs"] = (models.SharedChemistry.objects.filter(layer=layer, reactions__gte=20)
                                .exclude(identical=0).select_related("model_a", "model_b")
                                .order_by("-identical")[:30])
        return context


class SubMechanismList(TemplateView):
    """Every sub-mechanism, by layer: one row per family of models sharing that layer's chemistry."""
    template_name = "database/submechanism_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        layer = self.request.GET.get("layer", "")
        shared = self.request.GET.get("shared") == "1"
        rows = models.SubMechanism.objects.select_related("origin__source")
        context["layers"] = sorted(set(rows.values_list("layer", flat=True)), key=sub_mechanisms.layer_sort_key)
        context["total"] = rows.count()
        context["shared_total"] = rows.filter(model_count__gt=1).count()
        if layer:
            rows = rows.filter(layer=layer)
        if shared:
            rows = rows.filter(model_count__gt=1)
        groups = defaultdict(list)
        for row in sorted(rows, key=lambda r: (-r.model_count, r.default_name)):
            groups[row.layer].append(row)
        context["groups"] = sorted(groups.items(), key=lambda item: sub_mechanisms.layer_sort_key(item[0]))
        context["layer"], context["shared"] = layer, shared
        return context


class SubMechanismDetail(DetailView):
    """One sub-mechanism: its variants, how they compare with a reference variant, and reaction by reaction."""
    model = models.SubMechanism
    template_name = "database/submechanism_detail.html"
    context_object_name = "sub_mechanism"

    def get_queryset(self):
        return super().get_queryset().select_related("origin__source")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reference = self.request.GET.get("reference", "1")
        context.update(sub_mechanisms.compare(self.object, int(reference) if reference.isdigit() else 1))
        context["other_families"] = (models.SubMechanism.objects.filter(layer=self.object.layer, model_count__gt=1)
                                     .exclude(pk=self.object.pk).order_by("-model_count")[:12])
        return context


def _species_of_structures(structure_ids):
    """structure id -> the lowest-numbered species with that structure."""
    isomer_of = dict(models.Structure.objects.filter(pk__in=structure_ids).values_list("pk", "isomer_id"))
    species_of_isomer = {}
    for species_id, isomer_id in models.Species.isomers.through.objects.filter(
            isomer_id__in=set(isomer_of.values())).order_by("species_id").values_list("species_id", "isomer_id"):
        species_of_isomer.setdefault(isomer_id, species_id)
    return {pk: species_of_isomer.get(isomer) for pk, isomer in isomer_of.items()}


def _model_counts(reaction_ids):
    """reaction id -> number of models with a rate for it."""
    return dict(models.KineticsComment.objects.filter(kinetics__reaction_id__in=reaction_ids)
                .values_list("kinetics__reaction_id").annotate(n=Count("kinetic_model", distinct=True)))


class RMGLibraryList(TemplateView):
    """Every RMG-database library with entries on the site, and the model closest to each."""
    template_name = "database/rmg_library_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = {("kinetics", name): n for name, n in models.KineticsRecord.objects.filter(provider="rmg_library")
                   .values_list("library").annotate(n=Count("id"))}
        entries.update({("thermo", name): n for name, n in models.ThermoRecord.objects.filter(provider="rmg_thermo_library")
                        .values_list("raw_data__library").annotate(n=Count("id")) if name})
        best, related = {}, defaultdict(int)
        for overlap in models.ModelLibraryOverlap.objects.filter(identical__gt=0).select_related("kinetic_model"):
            key = (overlap.kind, overlap.library)
            related[key] += 1
            if key not in best or overlap.identical > best[key].identical:
                best[key] = overlap
        context["rows"] = [{"kind": kind, "name": name, "entries": n, "models": related.get((kind, name), 0),
                            "best": best.get((kind, name))}
                           for (kind, name), n in sorted(entries.items(), key=lambda item: (item[0][0], item[0][1].lower()))]
        return context


class RMGLibraryDetail(TemplateView):
    """One RMG-database library: the models that share its data and its entries matched on the site."""
    template_name = "database/rmg_library_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kind, name = kwargs["kind"], kwargs["name"]
        if kind not in ("kinetics", "thermo"):
            raise Http404
        if kind == "kinetics":
            entries = models.KineticsRecord.objects.filter(provider="rmg_library", library=name).order_by("pk")
        else:
            entries = models.ThermoRecord.objects.filter(provider="rmg_thermo_library", raw_data__library=name).order_by("label")
        overlaps = (models.ModelLibraryOverlap.objects.filter(library=name, kind=kind).select_related("kinetic_model")
                    .order_by("-identical", "-shared"))
        first = entries.first()
        if first is None and not overlaps.exists():
            raise Http404
        context["other_models"] = overlaps.filter(identical=0).count()
        overlaps = overlaps.filter(identical__gt=0)
        page = Paginator(entries, 100).get_page(self.request.GET.get("page"))
        rows = list(page.object_list)
        if kind == "kinetics":
            counts = _model_counts([r.reaction_id for r in rows])
            for row in rows:
                row.model_count = counts.get(row.reaction_id, 0)
                row.entry_url = rmg_matching.entry_url(row)
        else:
            species = _species_of_structures([r.structure_id for r in rows])
            for row in rows:
                row.species_id = species.get(row.structure_id)
        version = first.source_version if first else models.ModelLibraryOverlap.objects.filter(library=name).first().source_version
        context.update({"kind": kind, "name": name, "kind_label": "Reactions" if kind == "kinetics" else "Thermo",
                        "page": page, "rows": rows, "overlaps": overlaps, "version": version,
                        "links": rmg_matching.library_links(kind, name, version)})
        return context


class RMGFamilyList(TemplateView):
    """Every RMG reaction family that generates reactions on the site."""
    template_name = "database/rmg_family_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estimates = dict(models.KineticsRecord.objects.filter(provider="rmg_family").values_list("library")
                         .annotate(n=Count("id")))
        rows = (models.Reaction.objects.exclude(rmg_family__in=["", "-", "?"]).values_list("rmg_family")
                .annotate(reactions=Count("canonical_key", distinct=True)).order_by("-reactions", "rmg_family"))
        context["rows"] = [{"name": name, "reactions": n, "estimates": estimates.get(name, 0)} for name, n in rows]
        context["unclassified"] = models.Reaction.objects.filter(rmg_family="-").values("canonical_key").distinct().count()
        context["unsupported"] = models.Reaction.objects.filter(rmg_family="?").values("canonical_key").distinct().count()
        return context


class RMGFamilyDetail(TemplateView):
    """The site's reactions that one RMG family generates, one row per canonical reaction."""
    template_name = "database/rmg_family_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = kwargs["name"]
        reactions = (models.Reaction.objects.filter(rmg_family=name).exclude(canonical_key="")
                     .order_by("canonical_key", "pk").distinct("canonical_key").only("pk", "rmg_template", "layer"))
        if not reactions.exists():
            raise Http404
        page = Paginator(reactions, 100).get_page(self.request.GET.get("page"))
        rows = list(page.object_list)
        equations = chemistry_index.equations({r.pk: None for r in rows})
        counts = _model_counts([r.pk for r in rows])
        for row in rows:
            row.equation_text = equations.get(row.pk, row.pk)
            row.model_count = counts.get(row.pk, 0)
        estimate = models.KineticsRecord.objects.filter(provider="rmg_family", library=name).first()
        version = estimate.source_version if estimate else ""
        context.update({"name": name, "page": page, "rows": rows, "total": page.paginator.count,
                        "links": rmg_matching.family_links(name, version)})
        return context


class ChemistryBlockDetail(DetailView):
    """A block of identical rates used by exactly the same set of models."""
    model = models.ChemistryBlock
    template_name = "database/chemistry_block_detail.html"
    context_object_name = "chemistry_block"  # "block" is taken inside {% block %} tags

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        block = self.object
        context["block_models"] = sorted(block.kinetic_models.select_related("source"),
                                         key=lambda m: ((m.source.publication_year if m.source_id else "") or "9999", m.model_name))
        page = Paginator(block.reactions.order_by("layer", "pk").only("pk", "layer"), 200).get_page(self.request.GET.get("page"))
        rows = list(page.object_list)
        equations = chemistry_index.equations({r.pk: block.origin_id for r in rows})
        for row in rows:
            row.equation_text = equations.get(row.pk, row.pk)
        context.update({"page": page, "rows": rows})
        return context
