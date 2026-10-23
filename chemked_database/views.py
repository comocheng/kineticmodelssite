"""
ChemKED Database Views

Views for browsing and exploring experimental combustion data.
Designed for combustion research community and scientists.
"""

import html as html_mod
import os
import re
import tempfile
import logging
import json
import uuid
import yaml
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.db.models import Count, Avg, Min, Max, Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView, DetailView, ListView, FormView
from django.views.generic.edit import CreateView
from django_filters.views import FilterView
from .github_pr_service import verify_orcid, OrcidVerificationError
import requests as http_requests

from .models import (
    ExperimentDataset,
    ExperimentDatapoint,
    CommonProperties,
    Composition,
    CompositionSpecies,
    IgnitionDelayDatapoint,
    LaminarBurningVelocityMeasurementDatapoint,
    RateCoefficientDatapoint,
    ConcentrationTimeProfileMeasurementDatapoint,
    JetStirredReactorMeasurementDatapoint,
    OutletConcentrationMeasurementDatapoint,
    BurnerStabilizedFlameSpeciationMeasurementDatapoint,
    MeasurementType,
    Apparatus,
    FileAuthor,
    ReferenceAuthor,
    ValueWithUnit,
    ExperimentType,
    ApparatusKind,
    CompositionKind,
    Submission,
)
from .filters import DatasetFilter, DatapointFilter
from .forms import (
    FileMetadataForm,
    FileAuthorFormSet,
    ReferenceForm,
    ReferenceAuthorFormSet,
    ExperimentForm,
    CommonPropertiesForm,
    IgnitionInfoForm,
    CompositionSpeciesFormSet,
    DatapointFormSet,
    IgnitionDelayFormSet,
    LaminarBurningVelocityFormSet,
    RateCoefficientFormSet,
    JetStirredReactorFormSet,
    OutletConcentrationFormSet,
    ConcentrationTimeProfileFormSet,
    BurnerStabilizedFlameSpeciationFormSet,
    ChemKEDUploadForm,
    ExportOptionsForm,
)

logger = logging.getLogger(__name__)


def _unwrap_equiv(value):
    """Unwrap equivalence-ratio from list to scalar float.

    PyKED normalizes scalar equivalence-ratio values to single-element
    lists for schema validation.  The database expects a plain float.
    """
    if isinstance(value, list):
        return value[0] if value else None
    return value


# Normalise shorthand ignition-target labels to canonical choices.
_IGNITION_TARGET_ALIASES = {
    'p': 'pressure',
    'p;': 'pressure',
    't': 'temperature',
}


def _normalize_ignition_target(value):
    """Map shorthand target strings ('P', 'T', 'p;') to canonical names."""
    if not value:
        return value
    return _IGNITION_TARGET_ALIASES.get(value.lower().strip(), value)


def verify_orcid_view(request):
    """AJAX endpoint that verifies an ORCID via the public ORCID API.

    GET /chemked/verify-orcid/?orcid=0000-0000-0000-000X
    Returns JSON: {verified, name, orcid, error}
    """

    orcid = request.GET.get('orcid', '').strip()
    if not orcid:
        return JsonResponse({'verified': False, 'error': 'No ORCID provided.'}, status=400)

    try:
        result = verify_orcid(orcid)
        return JsonResponse(result)
    except OrcidVerificationError as exc:
        return JsonResponse({'verified': False, 'orcid': orcid, 'error': str(exc)})


def verify_github_username_view(request):
    """AJAX endpoint that checks whether a GitHub username exists.

    GET /chemked/verify-github/?username=octocat
    Returns JSON: {valid, username, name, avatar_url, error}
    """

    username = request.GET.get('username', '').strip().lstrip('@')
    if not username:
        return JsonResponse({'valid': False, 'error': 'No username provided.'}, status=400)

    # Basic format check – GitHub usernames: alphanumeric + hyphens, 1-39 chars
    if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$', username):
        return JsonResponse({
            'valid': False,
            'username': username,
            'error': 'Invalid GitHub username format.',
        })

    try:
        resp = http_requests.get(
            f'https://api.github.com/users/{username}',
            headers={'Accept': 'application/vnd.github.v3+json'},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return JsonResponse({
                'valid': True,
                'username': data.get('login', username),
                'name': data.get('name') or data.get('login', username),
                'avatar_url': data.get('avatar_url', ''),
            })
        elif resp.status_code == 404:
            return JsonResponse({
                'valid': False,
                'username': username,
                'error': f'GitHub user "{username}" not found.',
            })
        else:
            return JsonResponse({
                'valid': False,
                'username': username,
                'error': 'Could not verify (GitHub API returned %d).' % resp.status_code,
            })
    except http_requests.RequestException:
        return JsonResponse({
            'valid': False,
            'username': username,
            'error': 'Could not reach GitHub API.',
        })


class ChemKEDHomeView(TemplateView):
    """
    ChemKED database home page with overview statistics.
    """
    template_name = "chemked_database/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Overall statistics
        context["dataset_count"] = ExperimentDataset.objects.count()
        context["datapoint_count"] = ExperimentDatapoint.objects.count()
        context["species_count"] = CompositionSpecies.objects.values("species_name").distinct().count()

        # Experiment type breakdown
        context["experiment_types"] = (
            ExperimentDataset.objects
            .values("experiment_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Apparatus breakdown
        context["apparatus_types"] = (
            ExperimentDataset.objects
            .filter(apparatus__isnull=False)
            .values("apparatus__kind")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Temperature and pressure ranges
        temp_stats = ExperimentDatapoint.objects.aggregate(
            min_temp=Min("temperature"),
            max_temp=Max("temperature"),
            avg_temp=Avg("temperature"),
        )
        context["temp_stats"] = temp_stats

        pressure_stats = ExperimentDatapoint.objects.aggregate(
            min_pressure=Min("pressure"),
            max_pressure=Max("pressure"),
        )
        context["pressure_stats"] = pressure_stats

        # Recent datasets
        context["recent_datasets"] = ExperimentDataset.objects.order_by("-created_at")[:5]

        # Top fuels (species appearing most frequently)
        context["top_fuels"] = (
            CompositionSpecies.objects
            .exclude(species_name__in=["O2", "N2", "Ar", "He", "CO2", "H2O"])
            .values("species_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return context


class DatasetListView(FilterView):
    """
    Filterable list of ChemKED datasets.
    """
    model = ExperimentDataset
    filterset_class = DatasetFilter
    template_name = "chemked_database/dataset_list.html"
    context_object_name = "datasets"
    paginate_by = 25

    def get_queryset(self):
        return (
            ExperimentDataset.objects
            .select_related("apparatus")
            .prefetch_related("file_authors", "reference_authors")
            .annotate(datapoint_count=Count("datapoints", distinct=True))
            .order_by("-reference_year", "chemked_file_path")
        )

    def get_template_names(self):
        # Return partial template for AJAX requests
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return ["chemked_database/partials/dataset_table.html"]
        return [self.template_name]


class DatasetDetailView(DetailView):
    """
    Detailed view of a single ChemKED dataset.
    """
    model = ExperimentDataset
    template_name = "chemked_database/dataset_detail.html"
    context_object_name = "dataset"

    def get_queryset(self):
        return (
            ExperimentDataset.objects
            .select_related("apparatus", "common_properties", "common_properties__composition")
            .prefetch_related(
                "file_authors",
                "reference_authors",
                "datapoints",
                "datapoints__ignition_delay",
                "datapoints__temperature_quantity",
                "datapoints__pressure_quantity",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = self.object

        # Paginate datapoints
        datapoints = dataset.datapoints.select_related(
            "ignition_delay",
            "composition",
            "temperature_quantity",
            "pressure_quantity",
        ).order_by("temperature")

        page = self.request.GET.get("page", 1)
        paginator = Paginator(datapoints, 25)
        try:
            context["datapoints"] = paginator.page(page)
        except PageNotAnInteger:
            context["datapoints"] = paginator.page(1)
        except EmptyPage:
            context["datapoints"] = paginator.page(paginator.num_pages)

        # Common composition species
        if hasattr(dataset, "common_properties") and dataset.common_properties:
            common_props = dataset.common_properties
            context["common_properties"] = common_props
            if common_props.composition:
                context["common_species"] = common_props.composition.species.all()

        # Temperature and pressure ranges for this dataset
        context["temp_range"] = datapoints.aggregate(
            min_temp=Min("temperature"),
            max_temp=Max("temperature"),
        )
        context["pressure_range"] = datapoints.aggregate(
            min_pressure=Min("pressure"),
            max_pressure=Max("pressure"),
        )

        # Ignition delay range (if applicable)
        if dataset.experiment_type == ExperimentType.IGNITION_DELAY:
            ignition_stats = (
                IgnitionDelayDatapoint.objects
                .filter(datapoint__dataset=dataset, ignition_delay__isnull=False)
                .aggregate(
                    min_delay=Min("ignition_delay"),
                    max_delay=Max("ignition_delay"),
                )
            )
            context["ignition_stats"] = ignition_stats

        # Check if any datapoints have per-datapoint species composition data
        # (common for JSR, concentration profiles, etc.)
        context["has_species_data"] = datapoints.filter(
            composition__isnull=False
        ).exists()

        return context


class DatapointDetailView(DetailView):
    """
    Detailed view of a single experimental datapoint.
    """
    model = ExperimentDatapoint
    template_name = "chemked_database/datapoint_detail.html"
    context_object_name = "datapoint"

    def get_queryset(self):
        return (
            ExperimentDatapoint.objects
            .select_related(
                "dataset",
                "dataset__apparatus",
                "composition",
                "temperature_quantity",
                "pressure_quantity",
            )
            .prefetch_related(
                "time_histories",
                "composition__species",
                "composition__species__thermo_data",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        datapoint = self.object

        # Get composition species
        composition = datapoint.get_composition()
        if composition:
            context["composition"] = composition
            context["species_list"] = composition.species.select_related("thermo_data").all()

        # Get experiment-type extension
        if hasattr(datapoint, "ignition_delay"):
            context["ignition_delay"] = datapoint.ignition_delay
        if hasattr(datapoint, "laminar_burning_velocity_measurement"):
            context["laminar_burning_velocity_measurement"] = datapoint.laminar_burning_velocity_measurement
        if hasattr(datapoint, "concentration_time_profile_measurement"):
            context["concentration_time_profile_measurement"] = datapoint.concentration_time_profile_measurement
        if hasattr(datapoint, "jet_stirred_reactor_measurement"):
            context["jet_stirred_reactor_measurement"] = datapoint.jet_stirred_reactor_measurement
        if hasattr(datapoint, "outlet_concentration_measurement"):
            context["outlet_concentration_measurement"] = datapoint.outlet_concentration_measurement
        if hasattr(datapoint, "burner_stabilized_flame_speciation_measurement"):
            context["burner_stabilized_flame_speciation_measurement"] = datapoint.burner_stabilized_flame_speciation_measurement

        # RCM data
        if hasattr(datapoint, "rcm_data"):
            context["rcm_data"] = datapoint.rcm_data

        # Time histories
        context["time_histories"] = datapoint.time_histories.all()

        # Volume history
        if hasattr(datapoint, "volume_history"):
            context["volume_history"] = datapoint.volume_history

        return context


class SpeciesSearchView(ListView):
    """
    Search for species across all ChemKED compositions.
    """
    model = CompositionSpecies
    template_name = "chemked_database/species_search.html"
    context_object_name = "species_list"
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            CompositionSpecies.objects
            .values("species_name", "inchi", "smiles")
            .annotate(occurrence_count=Count("id"))
            .order_by("-occurrence_count")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(species_name__icontains=q) |
                Q(inchi__icontains=q) |
                Q(smiles__icontains=q)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class SpeciesDatapointsView(ListView):
    """
    Detailed view of a species with all its attributes and related datapoints.
    """
    model = ExperimentDatapoint
    template_name = "chemked_database/species_datapoints.html"
    context_object_name = "datapoints"
    paginate_by = 25

    def get_queryset(self):
        species_name = self.kwargs.get("species_name", "")
        return (
            ExperimentDatapoint.objects
            .filter(
                Q(composition__species__species_name=species_name) |
                Q(dataset__common_properties__composition__species__species_name=species_name)
            )
            .select_related("dataset", "ignition_delay", "temperature_quantity", "pressure_quantity")
            .distinct()
            .order_by("temperature")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        species_name = self.kwargs.get("species_name", "")
        context["species_name"] = species_name

        # Get species info from the first occurrence with complete data
        species_instance = (
            CompositionSpecies.objects
            .filter(species_name=species_name)
            .select_related("thermo_data", "database_species")
            .order_by("-inchi", "-smiles", "-atomic_composition")  # Prefer ones with identifiers
            .first()
        )
        context["species_info"] = species_instance

        # Get thermo data if available
        if species_instance:
            try:
                context["thermo_data"] = species_instance.thermo_data
            except CompositionSpecies.thermo_data.RelatedObjectDoesNotExist:
                context["thermo_data"] = None

            # Link to database Species if matched
            context["database_species"] = species_instance.database_species

        # Aggregate species statistics across all occurrences
        species_stats = (
            CompositionSpecies.objects
            .filter(species_name=species_name)
            .aggregate(
                occurrence_count=Count("id"),
                dataset_count=Count("composition__datapoints__dataset", distinct=True),
                avg_amount=Avg("amount"),
                min_amount=Min("amount"),
                max_amount=Max("amount"),
            )
        )
        context["species_stats"] = species_stats

        # Get all unique identifiers for this species
        identifiers = (
            CompositionSpecies.objects
            .filter(species_name=species_name)
            .filter(Q(inchi__gt="") | Q(smiles__gt=""))
            .values("inchi", "smiles")
            .distinct()
        )
        seen_identifiers = set()
        unique_identifiers = []
        for item in identifiers:
            inchi = (item.get("inchi") or "").strip()
            smiles = (item.get("smiles") or "").strip()
            key = (inchi, smiles)
            if key in seen_identifiers:
                continue
            seen_identifiers.add(key)
            unique_identifiers.append({"inchi": inchi, "smiles": smiles})
        context["all_identifiers"] = unique_identifiers

        primary_inchi = (species_instance.inchi or "").strip() if species_instance else ""
        primary_smiles = (species_instance.smiles or "").strip() if species_instance else ""
        primary_key = (primary_inchi, primary_smiles)
        alternative_identifiers = [
            ident for ident in unique_identifiers
            if (ident["inchi"], ident["smiles"]) != primary_key
        ]
        context["alternative_identifiers"] = alternative_identifiers

        # Temperature/pressure range for this species
        datapoints = self.get_queryset()
        context["temp_range"] = datapoints.aggregate(
            min_temp=Min("temperature"),
            max_temp=Max("temperature"),
        )
        context["pressure_range"] = datapoints.aggregate(
            min_pressure=Min("pressure"),
            max_pressure=Max("pressure"),
        )

        # Experiment type breakdown for this species
        context["experiment_types"] = (
            datapoints
            .values("dataset__experiment_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return context


class ApparatusListView(ListView):
    """
    List of apparatus with associated datasets.
    """
    model = Apparatus
    template_name = "chemked_database/apparatus_list.html"
    context_object_name = "apparatus_list"

    def get_queryset(self):
        return (
            Apparatus.objects
            .annotate(dataset_count=Count("datasets"))
            .order_by("-dataset_count")
        )


# =============================================================================
# Dataset Creation Views (Multi-Step Wizard)
# =============================================================================

class DatasetCreateWizardView(TemplateView):
    """
    Multi-step wizard for creating a new ChemKED dataset.
    Similar to ChemKED-gui with tabs for different sections.
    """
    template_name = "chemked_database/dataset_create.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Initialize all forms with session data or empty
        session_data = self.request.session.get('chemked_wizard', {})
        
        # File metadata forms
        context['file_metadata_form'] = FileMetadataForm(
            initial=session_data.get('file_metadata', {})
        )
        context['file_author_formset'] = FileAuthorFormSet(
            initial=session_data.get('file_authors', [{'name': '', 'orcid': ''}]),
            prefix='file_authors'
        )
        
        # Reference forms
        context['reference_form'] = ReferenceForm(
            initial=session_data.get('reference', {})
        )
        context['reference_author_formset'] = ReferenceAuthorFormSet(
            initial=session_data.get('reference_authors', [{'name': '', 'orcid': ''}]),
            prefix='ref_authors'
        )
        
        # Experiment & apparatus form
        context['experiment_form'] = ExperimentForm(
            initial=session_data.get('experiment', {})
        )
        
        # Common properties
        context['common_properties_form'] = CommonPropertiesForm(
            initial=session_data.get('common_properties', {})
        )
        context['ignition_info_form'] = IgnitionInfoForm(
            initial=session_data.get('ignition_info', {})
        )
        context['composition_species_formset'] = CompositionSpeciesFormSet(
            initial=session_data.get('composition_species', []),
            prefix='species'
        )
        
        # Datapoints
        context['datapoint_formset'] = DatapointFormSet(
            initial=session_data.get('datapoints', []),
            prefix='datapoints'
        )
        context['ignition_delay_formset'] = IgnitionDelayFormSet(
            initial=session_data.get('ignition_delays', []),
            prefix='ignition_delays'
        )
        context['lbv_formset'] = LaminarBurningVelocityFormSet(
            initial=session_data.get('lbv_data', []),
            prefix='lbv'
        )
        context['rate_coefficient_formset'] = RateCoefficientFormSet(
            initial=session_data.get('rate_coefficients', []),
            prefix='rate_coefficients'
        )
        context['jsr_formset'] = JetStirredReactorFormSet(
            initial=session_data.get('jsr_data', []),
            prefix='jsr'
        )
        context['outlet_concentration_formset'] = OutletConcentrationFormSet(
            initial=session_data.get('outlet_concentration_data', []),
            prefix='outlet_conc'
        )
        context['ctp_formset'] = ConcentrationTimeProfileFormSet(
            initial=session_data.get('ctp_data', []),
            prefix='ctp'
        )
        context['bsfs_formset'] = BurnerStabilizedFlameSpeciationFormSet(
            initial=session_data.get('bsfs_data', []),
            prefix='bsfs'
        )
        
        # Active tab (default to first)
        context['active_tab'] = self.request.GET.get('tab', 'metadata')
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle form submissions - save to session and validate."""
        action = request.POST.get('action', 'save')
        
        # Parse all forms
        file_metadata_form = FileMetadataForm(request.POST)
        file_author_formset = FileAuthorFormSet(request.POST, prefix='file_authors')
        reference_form = ReferenceForm(request.POST)
        reference_author_formset = ReferenceAuthorFormSet(request.POST, prefix='ref_authors')
        experiment_form = ExperimentForm(request.POST)
        common_properties_form = CommonPropertiesForm(request.POST)
        ignition_info_form = IgnitionInfoForm(request.POST)
        composition_species_formset = CompositionSpeciesFormSet(request.POST, prefix='species')
        datapoint_formset = DatapointFormSet(request.POST, prefix='datapoints')
        ignition_delay_formset = IgnitionDelayFormSet(request.POST, prefix='ignition_delays')
        lbv_formset = LaminarBurningVelocityFormSet(request.POST, prefix='lbv')
        rate_coefficient_formset = RateCoefficientFormSet(request.POST, prefix='rate_coefficients')
        jsr_formset = JetStirredReactorFormSet(request.POST, prefix='jsr')
        outlet_concentration_formset = OutletConcentrationFormSet(request.POST, prefix='outlet_conc')
        ctp_formset = ConcentrationTimeProfileFormSet(request.POST, prefix='ctp')
        bsfs_formset = BurnerStabilizedFlameSpeciationFormSet(request.POST, prefix='bsfs')
        
        # Collect data into session
        wizard_data = {
            'file_metadata': file_metadata_form.data if file_metadata_form.is_valid() else {},
            'file_authors': [f.cleaned_data for f in file_author_formset if f.is_valid() and f.cleaned_data],
            'reference': reference_form.cleaned_data if reference_form.is_valid() else {},
            'reference_authors': [f.cleaned_data for f in reference_author_formset if f.is_valid() and f.cleaned_data],
            'experiment': experiment_form.cleaned_data if experiment_form.is_valid() else {},
            'common_properties': common_properties_form.cleaned_data if common_properties_form.is_valid() else {},
            'ignition_info': ignition_info_form.cleaned_data if ignition_info_form.is_valid() else {},
            'composition_species': [f.cleaned_data for f in composition_species_formset if f.is_valid() and f.cleaned_data],
            'datapoints': [f.cleaned_data for f in datapoint_formset if f.is_valid() and f.cleaned_data],
            'ignition_delays': [f.cleaned_data for f in ignition_delay_formset if f.is_valid() and f.cleaned_data],
            'lbv_data': [f.cleaned_data for f in lbv_formset if f.is_valid() and f.cleaned_data],
            'rate_coefficients': [f.cleaned_data for f in rate_coefficient_formset if f.is_valid() and f.cleaned_data],
            'jsr_data': [f.cleaned_data for f in jsr_formset if f.is_valid() and f.cleaned_data],
            'outlet_concentration_data': [f.cleaned_data for f in outlet_concentration_formset if f.is_valid() and f.cleaned_data],
            'ctp_data': [f.cleaned_data for f in ctp_formset if f.is_valid() and f.cleaned_data],
            'bsfs_data': [f.cleaned_data for f in bsfs_formset if f.is_valid() and f.cleaned_data],
        }
        request.session['chemked_wizard'] = wizard_data
        
        if action == 'save_draft':
            messages.success(request, 'Draft saved to session.')
            return redirect(request.path)
        
        elif action == 'export_yaml':
            # Export as ChemKED YAML without saving to database
            return self._export_yaml(wizard_data)
        
        elif action == 'submit':
            # Validate all forms
            all_valid = all([
                file_metadata_form.is_valid(),
                file_author_formset.is_valid(),
                reference_form.is_valid(),
                reference_author_formset.is_valid(),
                experiment_form.is_valid(),
                common_properties_form.is_valid(),
                composition_species_formset.is_valid(),
                datapoint_formset.is_valid(),
            ])
            
            experiment_type = experiment_form.cleaned_data.get('experiment_type', '')
            if experiment_type == ExperimentType.IGNITION_DELAY:
                all_valid = all_valid and ignition_delay_formset.is_valid()
            elif experiment_type == ExperimentType.LAMINAR_BURNING_VELOCITY:
                all_valid = all_valid and lbv_formset.is_valid()
            elif experiment_type == ExperimentType.RATE_COEFFICIENT:
                all_valid = all_valid and rate_coefficient_formset.is_valid()
            elif experiment_type == ExperimentType.JSR_MEASUREMENT:
                all_valid = all_valid and jsr_formset.is_valid()
            elif experiment_type == ExperimentType.OUTLET_CONCENTRATION:
                all_valid = all_valid and outlet_concentration_formset.is_valid()
            elif experiment_type == ExperimentType.CONCENTRATION_TIME_PROFILE:
                all_valid = all_valid and ctp_formset.is_valid()
            elif experiment_type == ExperimentType.BSFS_MEASUREMENT:
                all_valid = all_valid and bsfs_formset.is_valid()
            
            if all_valid:
                try:
                    dataset = self._create_dataset(wizard_data)
                    # Clear session data
                    del request.session['chemked_wizard']
                    messages.success(request, f'Dataset created successfully with {dataset.datapoints.count()} datapoints.')
                    return redirect('chemked_database:dataset-detail', pk=dataset.pk)
                except Exception as e:
                    logger.exception("Error creating dataset")
                    messages.error(request, f'Error creating dataset: {str(e)}')
            else:
                messages.error(request, 'Please correct the errors below.')
        
        # Re-render with errors
        context = self.get_context_data(**kwargs)
        context.update({
            'file_metadata_form': file_metadata_form,
            'file_author_formset': file_author_formset,
            'reference_form': reference_form,
            'reference_author_formset': reference_author_formset,
            'experiment_form': experiment_form,
            'common_properties_form': common_properties_form,
            'ignition_info_form': ignition_info_form,
            'composition_species_formset': composition_species_formset,
            'datapoint_formset': datapoint_formset,
            'ignition_delay_formset': ignition_delay_formset,
            'lbv_formset': lbv_formset,
            'rate_coefficient_formset': rate_coefficient_formset,
            'jsr_formset': jsr_formset,
            'outlet_concentration_formset': outlet_concentration_formset,
            'ctp_formset': ctp_formset,
            'bsfs_formset': bsfs_formset,
        })
        return self.render_to_response(context)
    
    def _parse_value_with_unit(self, value_string):
        """
        Parse a string like '1249 K' or '529 us' into value and unit.
        Returns (value, unit) tuple.
        """
        if not value_string:
            return None, None
        
        value_string = value_string.strip()
        # Pattern: number followed by optional space and unit
        match = re.match(r'^([\d.eE+-]+)\s*(.*)$', value_string)
        if match:
            try:
                value = float(match.group(1))
                unit = match.group(2).strip() or 'dimensionless'
                return value, unit
            except ValueError:
                pass
        return None, value_string
    
    def _convert_to_si(self, value, unit):
        """
        Convert value to SI units. Returns (si_value, si_unit).
        Uses pint for unit conversion if available.
        """
        try:
            from pint import UnitRegistry
            ureg = UnitRegistry()
            quantity = value * ureg(unit)
            
            # Define SI base units for common quantities
            if quantity.dimensionality == {'[temperature]': 1}:
                si_quantity = quantity.to('kelvin')
            elif quantity.dimensionality == {'[pressure]': 1}:
                si_quantity = quantity.to('pascal')
            elif quantity.dimensionality == {'[time]': 1}:
                si_quantity = quantity.to('second')
            elif quantity.dimensionality == {'[length]': 1, '[time]': -1}:
                si_quantity = quantity.to('meter/second')
            else:
                si_quantity = quantity.to_base_units()
            
            return si_quantity.magnitude, str(si_quantity.units)
        except Exception as e:
            logger.warning(f"Unit conversion failed for {value} {unit}: {e}")
            return value, unit
    
    @transaction.atomic
    def _create_dataset(self, data):
        """Create ExperimentDataset and related models from wizard data."""
        
        # Get or create apparatus
        exp_data = data.get('experiment', {})
        apparatus, _ = Apparatus.objects.get_or_create(
            kind=exp_data.get('apparatus_kind', ApparatusKind.SHOCK_TUBE),
            institution=exp_data.get('apparatus_institution', ''),
            facility=exp_data.get('apparatus_facility', ''),
        )
        
        # Create dataset
        file_meta = data.get('file_metadata', {})
        ref_data = data.get('reference', {})
        
        # Create or update dataset
        wizard_path = f"user_created/{self.request.user.username if self.request.user.is_authenticated else 'anonymous'}/{ref_data.get('doi', 'no-doi')}"
        dataset, created = ExperimentDataset.objects.update_or_create(
            chemked_file_path=wizard_path,
            defaults=dict(
                file_version=file_meta.get('file_version', 0),
                chemked_version=file_meta.get('chemked_version', '0.4.1'),
                experiment_type=exp_data.get('experiment_type', ExperimentType.IGNITION_DELAY),
                apparatus=apparatus,
                reference_doi=ref_data.get('doi', ''),
                reference_journal=ref_data.get('journal', ''),
                reference_year=ref_data.get('year'),
                reference_volume=ref_data.get('volume'),
                reference_pages=ref_data.get('pages', ''),
                reference_detail=ref_data.get('detail', ''),
            ),
        )
        
        # If updating, clear old related objects so they get re-created
        if not created:
            dataset.datapoints.all().delete()
            dataset.file_authors.clear()
            dataset.reference_authors.clear()
            if hasattr(dataset, 'common_properties') and dataset.common_properties:
                dataset.common_properties.delete()
        
        # Add file authors
        for author_data in data.get('file_authors', []):
            if author_data.get('name'):
                author, created = FileAuthor.objects.get_or_create(
                    name=author_data['name'],
                    defaults={'orcid': author_data.get('orcid', '')},
                )
                if not created and author_data.get('orcid') and not author.orcid:
                    author.orcid = author_data['orcid']
                    author.save(update_fields=['orcid'])
                dataset.file_authors.add(author)
        
        # Add reference authors
        for author_data in data.get('reference_authors', []):
            if author_data.get('name'):
                author, _ = ReferenceAuthor.objects.get_or_create(
                    name=author_data['name'],
                    orcid=author_data.get('orcid', ''),
                )
                dataset.reference_authors.add(author)
        
        # Create common composition
        common_props_data = data.get('common_properties', {})
        species_data = data.get('composition_species', [])
        
        common_composition = None
        if species_data:
            common_composition = Composition.objects.create(
                kind=common_props_data.get('composition_kind', CompositionKind.MOLE_FRACTION)
            )
            for sp in species_data:
                if sp.get('species_name') and sp.get('amount') is not None:
                    CompositionSpecies.objects.create(
                        composition=common_composition,
                        species_name=sp['species_name'],
                        inchi=sp.get('inchi', ''),
                        smiles=sp.get('smiles', ''),
                        amount=sp['amount'],
                    )
        
        # Create common properties
        ignition_data = data.get('ignition_info', {})
        pressure = None
        pressure_quantity = None
        if common_props_data.get('pressure'):
            val, unit = self._parse_value_with_unit(common_props_data['pressure'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                pressure = si_val
                pressure_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        temperature = None
        temperature_quantity = None
        if common_props_data.get('temperature'):
            val, unit = self._parse_value_with_unit(common_props_data['temperature'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                temperature = si_val
                temperature_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        pressure_rise = None
        pressure_rise_quantity = None
        if common_props_data.get('pressure_rise'):
            val, unit = self._parse_value_with_unit(common_props_data['pressure_rise'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                pressure_rise = si_val
                pressure_rise_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        reactor_volume = None
        reactor_volume_quantity = None
        reactor_volume_units = 'm3'
        if common_props_data.get('reactor_volume'):
            val, unit = self._parse_value_with_unit(common_props_data['reactor_volume'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                reactor_volume = si_val
                reactor_volume_units = si_unit
                reactor_volume_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        residence_time = None
        residence_time_quantity = None
        residence_time_units = 's'
        if common_props_data.get('residence_time'):
            val, unit = self._parse_value_with_unit(common_props_data['residence_time'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                residence_time = si_val
                residence_time_units = si_unit
                residence_time_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        flow_rate = None
        flow_rate_quantity = None
        if common_props_data.get('flow_rate'):
            val, unit = self._parse_value_with_unit(common_props_data['flow_rate'])
            if val is not None:
                si_val, si_unit = self._convert_to_si(val, unit)
                flow_rate = si_val
                flow_rate_quantity = ValueWithUnit.objects.create(
                    value=val, units=unit
                )
        
        equivalence_ratio = _unwrap_equiv(common_props_data.get('equivalence_ratio'))
        equivalence_ratio_quantity = None
        if equivalence_ratio is not None:
            equivalence_ratio_quantity = ValueWithUnit.objects.create(
                value=equivalence_ratio, units='dimensionless'
            )
        
        common_properties = CommonProperties.objects.create(
            dataset=dataset,
            composition=common_composition,
            ignition_target=_normalize_ignition_target(ignition_data.get('ignition_target', '')),
            ignition_type=ignition_data.get('ignition_type', ''),
            pressure=pressure,
            pressure_quantity=pressure_quantity,
            pressure_rise=pressure_rise,
            pressure_rise_quantity=pressure_rise_quantity,
            temperature=temperature,
            temperature_quantity=temperature_quantity,
            reactor_volume=reactor_volume,
            reactor_volume_units=reactor_volume_units,
            reactor_volume_quantity=reactor_volume_quantity,
            residence_time=residence_time,
            residence_time_units=residence_time_units,
            residence_time_quantity=residence_time_quantity,
            flow_rate=flow_rate,
            flow_rate_quantity=flow_rate_quantity,
            equivalence_ratio=equivalence_ratio,
            equivalence_ratio_quantity=equivalence_ratio_quantity,
        )
        
        # Create datapoints
        datapoints_data = data.get('datapoints', [])
        ignition_delays_data = data.get('ignition_delays', [])
        lbv_data = data.get('lbv_data', [])
        rate_coefficients_data = data.get('rate_coefficients', [])
        jsr_data = data.get('jsr_data', [])
        outlet_concentration_data = data.get('outlet_concentration_data', [])
        ctp_data = data.get('ctp_data', [])
        bsfs_data = data.get('bsfs_data', [])
        
        for idx, dp_data in enumerate(datapoints_data):
            # Parse temperature
            temp_val, temp_unit = self._parse_value_with_unit(dp_data.get('temperature', ''))
            si_temp, _ = self._convert_to_si(temp_val, temp_unit) if temp_val else (None, None)
            
            temp_quantity = None
            if temp_val is not None:
                temp_quantity = ValueWithUnit.objects.create(
                    value=temp_val,
                    units=temp_unit,
                    uncertainty_type=dp_data.get('temperature_uncertainty_type', ''),
                    uncertainty=dp_data.get('temperature_uncertainty'),
                )
            
            # Parse pressure
            press_val, press_unit = self._parse_value_with_unit(dp_data.get('pressure', ''))
            si_press, _ = self._convert_to_si(press_val, press_unit) if press_val else (None, None)
            
            press_quantity = None
            if press_val is not None:
                press_quantity = ValueWithUnit.objects.create(
                    value=press_val,
                    units=press_unit,
                    uncertainty_type=dp_data.get('pressure_uncertainty_type', ''),
                    uncertainty=dp_data.get('pressure_uncertainty'),
                )
            
            # Create datapoint
            datapoint = ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=si_temp or 0,
                temperature_quantity=temp_quantity,
                pressure=si_press or 0,
                pressure_quantity=press_quantity,
                equivalence_ratio=_unwrap_equiv(dp_data.get('equivalence_ratio')),
                composition=common_composition,  # Use common composition
            )
            
            # Create experiment-type specific extension
            if dataset.experiment_type == ExperimentType.IGNITION_DELAY and idx < len(ignition_delays_data):
                ign_data = ignition_delays_data[idx]
                
                # Parse ignition delay
                ign_val, ign_unit = self._parse_value_with_unit(ign_data.get('ignition_delay', ''))
                si_ign, _ = self._convert_to_si(ign_val, ign_unit) if ign_val else (None, None)
                
                ign_quantity = None
                if ign_val is not None:
                    ign_quantity = ValueWithUnit.objects.create(
                        value=ign_val,
                        units=ign_unit,
                        uncertainty_type=ign_data.get('ignition_delay_uncertainty_type', ''),
                        uncertainty=ign_data.get('ignition_delay_uncertainty'),
                    )
                
                IgnitionDelayDatapoint.objects.create(
                    datapoint=datapoint,
                    ignition_delay=si_ign,
                    ignition_delay_quantity=ign_quantity,
                    ignition_target=_normalize_ignition_target(ign_data.get('ignition_target_override', '')),
                    ignition_type=ign_data.get('ignition_type_override', ''),
                )
            
            elif dataset.experiment_type == ExperimentType.LAMINAR_BURNING_VELOCITY and idx < len(lbv_data):
                lbv = lbv_data[idx]
                
                lbv_val, lbv_unit = self._parse_value_with_unit(lbv.get('laminar_burning_velocity', ''))
                si_lbv, _ = self._convert_to_si(lbv_val, lbv_unit) if lbv_val else (None, None)
                
                lbv_quantity = None
                if lbv_val is not None:
                    lbv_quantity = ValueWithUnit.objects.create(
                        value=lbv_val,
                        units=lbv_unit,
                        uncertainty_type=lbv.get('laminar_burning_velocity_uncertainty_type', ''),
                        uncertainty=lbv.get('laminar_burning_velocity_uncertainty'),
                    )
                
                LaminarBurningVelocityMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    laminar_burning_velocity=si_lbv,
                    laminar_burning_velocity_quantity=lbv_quantity,
                )
            
            elif dataset.experiment_type == ExperimentType.RATE_COEFFICIENT and idx < len(rate_coefficients_data):
                rc_data = rate_coefficients_data[idx]
                
                rc_val, rc_unit = self._parse_value_with_unit(rc_data.get('rate_coefficient', ''))
                
                rc_quantity = None
                if rc_val is not None:
                    rc_quantity = ValueWithUnit.objects.create(
                        value=rc_val,
                        units=rc_unit,
                        uncertainty_type=rc_data.get('rate_coefficient_uncertainty_type', ''),
                        uncertainty=rc_data.get('rate_coefficient_uncertainty'),
                    )
                
                RateCoefficientDatapoint.objects.create(
                    datapoint=datapoint,
                    measurement_type=rc_data.get('measurement_type', MeasurementType.RATE_COEFFICIENT),
                    rate_coefficient=rc_val,
                    rate_coefficient_units=rc_unit or 'cm3 mol-1 s-1',
                    rate_coefficient_quantity=rc_quantity,
                    reaction=rc_data.get('reaction', ''),
                    reaction_order=rc_data.get('reaction_order'),
                    bulk_gas=rc_data.get('bulk_gas', ''),
                    method=rc_data.get('method', ''),
                )
            
            elif dataset.experiment_type == ExperimentType.JSR_MEASUREMENT and idx < len(jsr_data):
                jsr = jsr_data[idx]
                
                env_temp = None
                env_temp_quantity = None
                if jsr.get('environment_temperature'):
                    env_val, env_unit = self._parse_value_with_unit(jsr['environment_temperature'])
                    if env_val is not None:
                        env_temp, _ = self._convert_to_si(env_val, env_unit)
                        env_temp_quantity = ValueWithUnit.objects.create(
                            value=env_val, units=env_unit
                        )
                
                JetStirredReactorMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    environment_temperature=env_temp,
                    environment_temperature_quantity=env_temp_quantity,
                )
            
            elif dataset.experiment_type == ExperimentType.OUTLET_CONCENTRATION and idx < len(outlet_concentration_data):
                oc_data = outlet_concentration_data[idx]
                
                oc_res_time = None
                oc_res_time_quantity = None
                if oc_data.get('residence_time'):
                    rt_val, rt_unit = self._parse_value_with_unit(oc_data['residence_time'])
                    if rt_val is not None:
                        oc_res_time, _ = self._convert_to_si(rt_val, rt_unit)
                        oc_res_time_quantity = ValueWithUnit.objects.create(
                            value=rt_val, units=rt_unit
                        )
                
                oc_vol_flow = None
                oc_vol_flow_quantity = None
                if oc_data.get('volumetric_flow'):
                    vf_val, vf_unit = self._parse_value_with_unit(oc_data['volumetric_flow'])
                    if vf_val is not None:
                        oc_vol_flow, _ = self._convert_to_si(vf_val, vf_unit)
                        oc_vol_flow_quantity = ValueWithUnit.objects.create(
                            value=vf_val, units=vf_unit
                        )
                
                OutletConcentrationMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    residence_time=oc_res_time,
                    residence_time_quantity=oc_res_time_quantity,
                    volumetric_flow_in_reference_state=oc_vol_flow,
                    volumetric_flow_quantity=oc_vol_flow_quantity,
                )
            
            elif dataset.experiment_type == ExperimentType.CONCENTRATION_TIME_PROFILE and idx < len(ctp_data):
                ctp = ctp_data[idx]
                
                # Parse values_text into list of [time, value] pairs
                values = []
                values_text = ctp.get('values_text', '')
                for line in values_text.strip().splitlines():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        try:
                            values.append([float(parts[0]), float(parts[1])])
                        except ValueError:
                            continue
                
                timeshift_amount_val = None
                timeshift_amount_quantity = None
                if ctp.get('timeshift_amount'):
                    ts_val, ts_unit = self._parse_value_with_unit(ctp['timeshift_amount'])
                    if ts_val is not None:
                        timeshift_amount_val = ts_val
                        timeshift_amount_quantity = ValueWithUnit.objects.create(
                            value=ts_val, units=ts_unit
                        )
                
                ConcentrationTimeProfileMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    time_units=ctp.get('time_units', 's'),
                    quantity_units=ctp.get('quantity_units', ''),
                    values=values,
                    uncertainty_type=ctp.get('uncertainty_type', ''),
                    uncertainty_value=ctp.get('uncertainty_value'),
                    timeshift_target=ctp.get('timeshift_target', ''),
                    timeshift_type=ctp.get('timeshift_type', ''),
                    timeshift_amount=timeshift_amount_val,
                    timeshift_amount_quantity=timeshift_amount_quantity,
                )
            
            elif dataset.experiment_type == ExperimentType.BSFS_MEASUREMENT and idx < len(bsfs_data):
                bsfs = bsfs_data[idx]
                
                dist_val = None
                dist_quantity = None
                if bsfs.get('distance'):
                    d_val, d_unit = self._parse_value_with_unit(bsfs['distance'])
                    if d_val is not None:
                        dist_val, _ = self._convert_to_si(d_val, d_unit)
                        dist_quantity = ValueWithUnit.objects.create(
                            value=d_val, units=d_unit
                        )
                
                bsfs_flow_rate = None
                bsfs_flow_rate_quantity = None
                if bsfs.get('flow_rate'):
                    fr_val, fr_unit = self._parse_value_with_unit(bsfs['flow_rate'])
                    if fr_val is not None:
                        bsfs_flow_rate, _ = self._convert_to_si(fr_val, fr_unit)
                        bsfs_flow_rate_quantity = ValueWithUnit.objects.create(
                            value=fr_val, units=fr_unit
                        )
                
                BurnerStabilizedFlameSpeciationMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    distance=dist_val,
                    distance_quantity=dist_quantity,
                    flow_rate=bsfs_flow_rate,
                    flow_rate_quantity=bsfs_flow_rate_quantity,
                )
        
        return dataset
    
    def _export_yaml(self, data):
        """Generate ChemKED YAML from wizard data and return as file download."""
        try:
            from pyked import chemked
            
            # Build the ChemKED dictionary
            chemked_dict = self._build_chemked_dict(data)
            
            # Create ChemKED object and write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                temp_path = f.name
            
            try:
                ck = chemked.ChemKED(dict_input=chemked_dict, skip_validation=False)
                ck.write_file(temp_path, overwrite=True)
                
                with open(temp_path, 'r') as f:
                    yaml_content = f.read()
                
                response = HttpResponse(yaml_content, content_type='application/x-yaml')
                response['Content-Disposition'] = 'attachment; filename="chemked_dataset.yaml"'
                return response
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except ImportError:
            messages.error(self.request, 'PyKED is not installed. Cannot export YAML.')
            return redirect(self.request.path)
        except Exception as e:
            logger.exception("Error exporting YAML")
            messages.error(self.request, f'Error exporting YAML: {str(e)}')
            return redirect(self.request.path)
    
    def _build_chemked_dict(self, data):
        """Build a ChemKED-compatible dictionary from wizard data."""
        file_meta = data.get('file_metadata', {})
        ref_data = data.get('reference', {})
        exp_data = data.get('experiment', {})
        common_props = data.get('common_properties', {})
        ignition_info = data.get('ignition_info', {})
        species_data = data.get('composition_species', [])
        datapoints_data = data.get('datapoints', [])
        ignition_delays = data.get('ignition_delays', [])
        lbv_data = data.get('lbv_data', [])
        rate_coefficients = data.get('rate_coefficients', [])
        jsr_data = data.get('jsr_data', [])
        outlet_concentration_data = data.get('outlet_concentration_data', [])
        ctp_data = data.get('ctp_data', [])
        bsfs_data = data.get('bsfs_data', [])
        
        experiment_type = exp_data.get('experiment_type', 'ignition delay')
        
        # File authors
        file_authors = []
        for auth in data.get('file_authors', []):
            author_dict = {'name': auth.get('name', '')}
            if auth.get('orcid'):
                author_dict['ORCID'] = auth['orcid']
            file_authors.append(author_dict)
        
        # Reference authors
        ref_authors = []
        for auth in data.get('reference_authors', []):
            author_dict = {'name': auth.get('name', '')}
            if auth.get('orcid'):
                author_dict['ORCID'] = auth['orcid']
            ref_authors.append(author_dict)
        
        # Build composition
        composition = {
            'kind': common_props.get('composition_kind', 'mole fraction'),
            'species': []
        }
        for sp in species_data:
            species_entry = {
                'species-name': sp.get('species_name', ''),
                'amount': [float(sp.get('amount', 0))]
            }
            if sp.get('inchi'):
                species_entry['InChI'] = sp['inchi']
            composition['species'].append(species_entry)
        
        # Build ignition type (for ignition delay only)
        ignition_type = {}
        if ignition_info.get('ignition_target'):
            ignition_type['target'] = ignition_info['ignition_target']
        if ignition_info.get('ignition_type'):
            ignition_type['type'] = ignition_info['ignition_type']
        
        # Build common-properties
        common_properties_dict = {
            'composition': composition,
        }
        if ignition_type:
            common_properties_dict['ignition-type'] = ignition_type
        if common_props.get('pressure'):
            common_properties_dict['pressure'] = [common_props['pressure']]
        if common_props.get('temperature'):
            common_properties_dict['temperature'] = [common_props['temperature']]
        if common_props.get('pressure_rise'):
            common_properties_dict['pressure-rise'] = [common_props['pressure_rise']]
        if common_props.get('equivalence_ratio'):
            common_properties_dict['equivalence-ratio'] = common_props['equivalence_ratio']
        if common_props.get('reactor_volume'):
            common_properties_dict['reactor-volume'] = [common_props['reactor_volume']]
        if common_props.get('residence_time'):
            common_properties_dict['residence-time'] = [common_props['residence_time']]
        if common_props.get('flow_rate'):
            common_properties_dict['flow-rate'] = [common_props['flow_rate']]
        
        # Build datapoints
        datapoints = []
        for idx, dp in enumerate(datapoints_data):
            dp_dict = {}
            
            # Temperature
            if dp.get('temperature'):
                dp_dict['temperature'] = [dp['temperature']]
                if dp.get('temperature_uncertainty') and dp.get('temperature_uncertainty_type'):
                    dp_dict['temperature'].append({
                        'uncertainty-type': dp['temperature_uncertainty_type'],
                        'uncertainty': dp['temperature_uncertainty']
                    })
            
            # Pressure
            if dp.get('pressure'):
                dp_dict['pressure'] = [dp['pressure']]
                if dp.get('pressure_uncertainty') and dp.get('pressure_uncertainty_type'):
                    dp_dict['pressure'].append({
                        'uncertainty-type': dp['pressure_uncertainty_type'],
                        'uncertainty': dp['pressure_uncertainty']
                    })
            
            # Equivalence ratio
            if dp.get('equivalence_ratio'):
                dp_dict['equivalence-ratio'] = dp['equivalence_ratio']
            
            # Composition (reference to common)
            dp_dict['composition'] = composition
            
            # Ignition type (reference to common)
            if ignition_type:
                dp_dict['ignition-type'] = ignition_type
            
            # Experiment-type-specific fields
            if experiment_type == ExperimentType.IGNITION_DELAY and idx < len(ignition_delays):
                ign = ignition_delays[idx]
                if ign.get('ignition_delay'):
                    dp_dict['ignition-delay'] = [ign['ignition_delay']]
                    if ign.get('ignition_delay_uncertainty') and ign.get('ignition_delay_uncertainty_type'):
                        dp_dict['ignition-delay'].append({
                            'uncertainty-type': ign['ignition_delay_uncertainty_type'],
                            'uncertainty': ign['ignition_delay_uncertainty']
                        })
            
            elif experiment_type == ExperimentType.LAMINAR_BURNING_VELOCITY and idx < len(lbv_data):
                lbv = lbv_data[idx]
                if lbv.get('laminar_burning_velocity'):
                    dp_dict['laminar-burning-velocity'] = [lbv['laminar_burning_velocity']]
                    if lbv.get('laminar_burning_velocity_uncertainty') and lbv.get('laminar_burning_velocity_uncertainty_type'):
                        dp_dict['laminar-burning-velocity'].append({
                            'uncertainty-type': lbv['laminar_burning_velocity_uncertainty_type'],
                            'uncertainty': lbv['laminar_burning_velocity_uncertainty']
                        })
            
            elif experiment_type == ExperimentType.RATE_COEFFICIENT and idx < len(rate_coefficients):
                rc = rate_coefficients[idx]
                if rc.get('rate_coefficient'):
                    dp_dict['rate-coefficient'] = [rc['rate_coefficient']]
                    if rc.get('rate_coefficient_uncertainty') and rc.get('rate_coefficient_uncertainty_type'):
                        dp_dict['rate-coefficient'].append({
                            'uncertainty-type': rc['rate_coefficient_uncertainty_type'],
                            'uncertainty': rc['rate_coefficient_uncertainty']
                        })
                if rc.get('reaction'):
                    dp_dict['reaction'] = rc['reaction']
                if rc.get('reaction_order'):
                    dp_dict['reaction-order'] = rc['reaction_order']
                if rc.get('bulk_gas'):
                    dp_dict['bulk-gas'] = rc['bulk_gas']
                if rc.get('method'):
                    dp_dict['method'] = rc['method']
            
            elif experiment_type == ExperimentType.JSR_MEASUREMENT and idx < len(jsr_data):
                jsr = jsr_data[idx]
                if jsr.get('environment_temperature'):
                    dp_dict['environment-temperature'] = [jsr['environment_temperature']]
            
            elif experiment_type == ExperimentType.OUTLET_CONCENTRATION and idx < len(outlet_concentration_data):
                oc = outlet_concentration_data[idx]
                if oc.get('residence_time'):
                    dp_dict['residence-time'] = [oc['residence_time']]
                if oc.get('volumetric_flow'):
                    dp_dict['volumetric-flow-in-reference-state'] = [oc['volumetric_flow']]
            
            elif experiment_type == ExperimentType.CONCENTRATION_TIME_PROFILE and idx < len(ctp_data):
                ctp = ctp_data[idx]
                if ctp.get('tracked_species_name'):
                    dp_dict['tracked-species'] = ctp['tracked_species_name']
                if ctp.get('quantity_units'):
                    dp_dict['quantity-units'] = ctp['quantity_units']
                if ctp.get('time_units'):
                    dp_dict['time-units'] = ctp['time_units']
            
            elif experiment_type == ExperimentType.BSFS_MEASUREMENT and idx < len(bsfs_data):
                bsfs = bsfs_data[idx]
                if bsfs.get('distance'):
                    dp_dict['distance'] = [bsfs['distance']]
                if bsfs.get('flow_rate'):
                    dp_dict['flow-rate'] = [bsfs['flow_rate']]
            
            datapoints.append(dp_dict)
        
        # Build apparatus dict
        apparatus_dict = {
            'kind': exp_data.get('apparatus_kind', 'shock tube'),
        }
        if exp_data.get('apparatus_mode'):
            apparatus_dict['mode'] = exp_data['apparatus_mode']
        if exp_data.get('apparatus_institution'):
            apparatus_dict['institution'] = exp_data['apparatus_institution']
        if exp_data.get('apparatus_facility'):
            apparatus_dict['facility'] = exp_data['apparatus_facility']
        
        # Build final dictionary
        chemked_dict = {
            'file-version': int(file_meta.get('file_version', 0)),
            'chemked-version': file_meta.get('chemked_version', '0.4.1'),
            'file-authors': file_authors,
            'reference': {
                'doi': ref_data.get('doi', ''),
                'authors': ref_authors,
                'journal': ref_data.get('journal', ''),
                'year': int(ref_data.get('year', 2020)),
                'volume': int(ref_data.get('volume', 1)) if ref_data.get('volume') else None,
                'pages': ref_data.get('pages', ''),
                'detail': ref_data.get('detail', ''),
            },
            'experiment-type': experiment_type,
            'apparatus': apparatus_dict,
            'common-properties': common_properties_dict,
            'datapoints': datapoints,
        }
        
        # Remove empty values
        if not chemked_dict['reference'].get('volume'):
            del chemked_dict['reference']['volume']
        
        return chemked_dict


def format_chemked_yaml(chemked_dict):
    """Serialize a ChemKED property dict to YAML matching database conventions.

    Delegates to ``pyked.batch_convert.yaml_dump`` — the same serializer that
    produced every file in ChemKED-database — so output is byte-identical.
    """
    from io import StringIO
    from pyked.batch_convert import yaml_dump

    d = dict(chemked_dict)
    d.pop('file-type', None)          # internal-only key

    buf = StringIO()
    yaml_dump(d, buf)
    return buf.getvalue()


def _sort_keys(obj):
    """Recursively sort dict keys so both sides of a diff share the same order."""
    if isinstance(obj, dict):
        return {k: _sort_keys(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [_sort_keys(item) for item in obj]
    return obj


def _normalize_yaml(content):
    """Parse and re-serialize YAML to get consistent formatting for diffing.

    Dict keys are sorted so that key-order differences between files do not
    cause false diff lines.  Returns the normalized string, or the original
    content if parsing fails.
    """
    try:
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            return format_chemked_yaml(_sort_keys(parsed))
    except Exception:
        pass
    return content


def _repo_folder(gh, filename, content, dup, allow_api=True):
    """Repository folder a contribution goes to, and why, for the upload preview.

    Returns {'dir': str, 'reason': str}, or None when it is not known (no local
    ChemKED-database clone and *allow_api* is False).
    """
    if dup:
        return {'dir': os.path.dirname(dup['path']), 'reason': 'The matching file is in this folder.'}
    suggestion = gh.suggest_folder(content)
    if suggestion is not None:
        return {'dir': suggestion.directory, 'reason': suggestion.reason}
    if not allow_api:
        return None
    return {'dir': os.path.dirname(gh.determine_repo_path(filename, content)), 'reason': ''}


def _compute_diff(existing_content, new_content, from_path, to_path, max_lines=None):
    """Compute a classified diff between two YAML strings.

    Both sides are normalized through ``format_chemked_yaml`` (with sorted
    keys) so that formatting-only differences are eliminated and only
    semantic changes appear in the diff.

    Uses ``SequenceMatcher(autojunk=False)`` so that frequently-repeated
    YAML lines (``species:``, ``amount:``, etc.) are not treated as junk
    and incorrectly shown as changed.

    Returns ``(classified, truncated, total_lines)`` where *classified* is a
    list of ``{'text': str, 'kind': str}`` dicts, *truncated* indicates
    whether the list was capped, and *total_lines* is the count before
    truncation.
    """
    from difflib import SequenceMatcher

    norm_existing = _normalize_yaml(existing_content)
    norm_new = _normalize_yaml(new_content)

    old_lines = norm_existing.splitlines()
    new_lines = norm_new.splitlines()

    sm = SequenceMatcher(None, old_lines, new_lines, autojunk=False)

    classified = [
        {'text': f'--- {from_path}', 'kind': 'header'},
        {'text': f'+++ {to_path}', 'kind': 'header'},
    ]
    for group in sm.get_grouped_opcodes(n=3):
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]
        classified.append({
            'text': f'@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@',
            'kind': 'hunk',
        })
        for tag, si1, si2, sj1, sj2 in group:
            if tag == 'equal':
                for line in old_lines[si1:si2]:
                    classified.append({'text': ' ' + line, 'kind': 'ctx'})
            if tag in ('replace', 'delete'):
                for line in old_lines[si1:si2]:
                    classified.append({'text': '-' + line, 'kind': 'del'})
            if tag in ('replace', 'insert'):
                for line in new_lines[sj1:sj2]:
                    classified.append({'text': '+' + line, 'kind': 'add'})

    total_lines = len(classified)
    truncated = False
    if max_lines and total_lines > max_lines:
        truncated = True
        classified = classified[:max_lines]

    return classified, truncated, total_lines


class DatasetUploadView(FormView):
    """
    View for uploading existing ChemKED YAML or ReSpecTh XML files.
    Parses the file and imports into the database.
    Supports both ReSpecTh v1.x (via PyKED) and v2.x (via custom converter).
    
    For ReSpecTh files, shows a preview step where user can edit the dataset name.
    """
    template_name = "chemked_database/dataset_upload.html"
    form_class = ChemKEDUploadForm
    success_url = reverse_lazy('chemked_database:dataset-upload')
    
    def get(self, request, *args, **kwargs):
        """Handle GET request - check if we're in preview mode or cancelling."""
        # Handle cancel - clean up temp file and session
        if 'cancel' in request.GET:
            return self._cancel_preview(request)
        
        if 'preview' in request.GET and request.session.get('respecth_preview'):
            return self._show_preview(request)
        return super().get(request, *args, **kwargs)
    
    def _cancel_preview(self, request):
        """Cancel the preview and clean up temp file."""
        preview_data = request.session.get('respecth_preview', {})
        temp_file_path = preview_data.get('temp_file_path', '')
        
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        # Clear session data
        if 'respecth_preview' in request.session:
            del request.session['respecth_preview']
        
        messages.info(request, 'Import cancelled.')
        return redirect('chemked_database:dataset-upload')
    
    def post(self, request, *args, **kwargs):
        """Handle POST - either initial upload or preview confirmation."""
        if 'confirm_import' in request.POST:
            return self._confirm_import(request)
        return super().post(request, *args, **kwargs)
    
    def _show_preview(self, request):
        """Show the preview page with editable dataset name."""
        from .forms import ReSpecThPreviewForm
        
        preview_data = request.session.get('respecth_preview', {})
        form = ReSpecThPreviewForm(initial=preview_data)
        
        context = self.get_context_data()
        context['preview_mode'] = True
        context['preview_form'] = form
        context['preview_data'] = preview_data
        
        return self.render_to_response(context)
    
    def _confirm_import(self, request):
        """Confirm the import after preview."""
        from .forms import ReSpecThPreviewForm
        
        form = ReSpecThPreviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Invalid form data. Please try again.')
            return redirect('chemked_database:dataset-upload')
        
        dataset_name = form.cleaned_data['dataset_name']
        temp_file_path = form.cleaned_data['temp_file_path']
        file_type = form.cleaned_data['file_type']
        original_filename = form.cleaned_data['original_filename']
        file_author = form.cleaned_data.get('file_author', '')
        
        # Retrieve GitHub contribution fields stored during preview
        preview_data = request.session.get('respecth_preview', {})
        contribute_to_github = preview_data.get('contribute_to_github', False)
        run_pyteck = preview_data.get('run_pyteck', False)
        github_username = preview_data.get('github_username', '')
        contribution_description = preview_data.get('contribution_description', '')
        file_author_orcid = form.cleaned_data.get('file_author_orcid', '') or preview_data.get('file_author_orcid', '')
        
        # Clear session data
        if 'respecth_preview' in request.session:
            del request.session['respecth_preview']
        
        # Check if temp file still exists
        if not os.path.exists(temp_file_path):
            messages.error(request, 'Temporary file expired. Please upload the file again.')
            return redirect('chemked_database:dataset-upload')
        
        pr_result = None
        try:
            from .chemked_adapter import ChemKEDDictAdapter

            if file_type == 'yaml':
                # YAML files: load directly as ChemKED dict
                with open(temp_file_path, 'r') as fh:
                    chemked_dict = yaml.safe_load(fh)
            else:
                # XML files: convert via batch_convert
                from pyked.batch_convert import convert_file
                chemked_dict = convert_file(temp_file_path, original_filename=original_filename)

            data = ChemKEDDictAdapter(chemked_dict)
            
            # Warn about potential duplicates but proceed — the GitHub PR
            # will show a diff for maintainers to review.
            if data.file_doi:
                existing = ExperimentDataset.objects.filter(file_doi=data.file_doi).first()
                if existing:
                    messages.info(
                        request,
                        f'Note: A dataset with DOI "{data.file_doi}" already exists '
                        f'as "{existing.chemked_file_path}". The contribution PR will '
                        'show any differences for review.'
                    )
            
            # Import with the unified ChemKED dict importer
            dataset = self._import_from_chemked_dict(chemked_dict, original_filename, file_author, custom_name=dataset_name)
            
            messages.success(
                request,
                f'Successfully imported "{original_filename}" as "{dataset.chemked_file_path}" '
                f'with {dataset.datapoints.count()} datapoints.'
            )
            
            # Create GitHub PR using the converter dict directly.
            # Avoids re-exporting from the DB which introduces Django
            # enum serialization bugs (!!python/object/apply tags).
            if contribute_to_github:
                pr_result = self._create_contribution_pr_from_chemked_dict(
                    chemked_dict,
                    dataset.chemked_file_path,
                    file_author, file_author_orcid,
                    run_pyteck, contribution_description,
                    github_username=github_username,
                )
                if pr_result:
                    messages.success(
                        request,
                        f'GitHub PR #{pr_result["pr_number"]} created: {pr_result["pr_url"]}'
                    )
            
            submission = Submission.objects.create(
                status=Submission.Status.SUCCESS,
                successful_imports=[{
                    'filename': original_filename,
                    'dataset_id': dataset.pk,
                    'dataset_name': dataset.chemked_file_path,
                    'datapoints': dataset.datapoints.count(),
                }],
                contributor_name=file_author,
                contributor_orcid=file_author_orcid,
                pr_url=pr_result.get('pr_url', '') if pr_result else '',
                pr_number=pr_result.get('pr_number') if pr_result else None,
                branch=pr_result.get('branch', '') if pr_result else '',
            )
            return redirect('chemked_database:submission-status', pk=submission.pk)
            
        except Exception as e:
            logger.exception("Error during confirmed import")
            formatted = self._format_import_error(str(e))
            level = messages.warning if formatted['kind'] == 'skipped' else messages.error
            level(request, formatted['message'])
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
        return redirect('chemked_database:dataset-upload')
    
    def form_valid(self, form):
        # Check if this is an AJAX request (for SSE-based progress)
        is_ajax = self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Get all uploaded files (supports multiple file upload)
        data_files = self.request.FILES.getlist('data_file')
        file_format = form.cleaned_data.get('file_format', 'auto')
        validate = form.cleaned_data.get('validate_on_upload', True)
        file_author = form.cleaned_data.get('file_author', '')
        file_author_orcid = form.cleaned_data.get('file_author_orcid', '')
        contribute_to_github = form.cleaned_data.get('contribute_to_github', False)
        run_pyteck = form.cleaned_data.get('run_pyteck', False)
        github_username = form.cleaned_data.get('github_username', '')
        contribution_description = form.cleaned_data.get('contribution_description', '')

        if not data_files:
            if is_ajax:
                return JsonResponse(
                    {
                        'success': False,
                        'batch_id': None,
                        'messages': [
                            {
                                'level': 'error',
                                'text': 'No files were received by the server. Please try selecting the files again.'
                            }
                        ]
                    },
                    status=400,
                )
            return self.form_invalid(form)
        
        # Single-file upload: always shows preview first (both XML and YAML).
        # The JS upload handler already follows redirects via xhr.responseURL.
        if len(data_files) == 1:
            return self._process_single_file(
                data_files[0], file_format, validate, file_author, file_author_orcid, form,
                contribute_to_github=contribute_to_github,
                run_pyteck=run_pyteck,
                github_username=github_username,
                contribution_description=contribution_description,
            )
        
        # For AJAX requests: Save files to temp storage and return batch_id for SSE processing
        if is_ajax:
            return self._prepare_batch_for_sse(
                data_files, file_format, validate, file_author, file_author_orcid,
                contribute_to_github=contribute_to_github,
                run_pyteck=run_pyteck,
                github_username=github_username,
                contribution_description=contribution_description,
            )
        
        # Non-AJAX multi-file: process synchronously
        successful_imports = []
        skipped_imports = []
        failed_imports = []
        
        for data_file in data_files:
            result = self._process_file_batch(
                data_file, file_format, validate, file_author, file_author_orcid
            )
            if result['success']:
                successful_imports.append(result)
            else:
                if result.get('error_kind') == 'skipped':
                    skipped_imports.append(result)
                else:
                    failed_imports.append(result)
        
        # Non-AJAX: use messages framework
        if successful_imports:
            total_datapoints = sum(r.get('datapoints', 0) for r in successful_imports)
            messages.success(
                self.request,
                f'Successfully imported {len(successful_imports)} dataset(s) with {total_datapoints} total datapoints.'
            )

            # Create GitHub PR if requested
            if contribute_to_github:
                pr_result = self._create_contribution_pr(
                    data_files, successful_imports,
                    file_author, file_author_orcid,
                    run_pyteck, contribution_description,
                    github_username=github_username,
                )
                if pr_result:
                    messages.success(
                        self.request,
                        f'GitHub PR #{pr_result["pr_number"]} created: {pr_result["pr_url"]}'
                    )
        
        if failed_imports:
            details = "\n".join(
                f'- {fail["filename"]}: {fail["error"]}' for fail in failed_imports
            )
            messages.error(
                self.request,
                f'Failed to import {len(failed_imports)} file(s):\n{details}'
            )

        if skipped_imports:
            details = "\n".join(
                f'- {skip["filename"]}: {skip["error"]}' for skip in skipped_imports
            )
            messages.warning(
                self.request,
                f'Skipped {len(skipped_imports)} file(s):\n{details}'
            )
        
        if successful_imports:
            submission = Submission.objects.create(
                status=Submission.Status.SUCCESS if not failed_imports else Submission.Status.PARTIAL,
                successful_imports=successful_imports,
                failed_imports=failed_imports,
                skipped_imports=skipped_imports,
                contributor_name=file_author,
                contributor_orcid=file_author_orcid,
                pr_url=pr_result.get('pr_url', '') if pr_result else '',
                pr_number=pr_result.get('pr_number') if pr_result else None,
                branch=pr_result.get('branch', '') if pr_result else '',
            )
            return redirect('chemked_database:submission-status', pk=submission.pk)
        return self.form_invalid(form)
    
    def _prepare_batch_for_sse(self, data_files, file_format, validate, file_author, file_author_orcid,
                              contribute_to_github=False, run_pyteck=False,
                              github_username='', contribution_description=''):
        """
        Save uploaded files to temp storage and return batch_id for SSE processing.
        This allows the client to track real-time progress via Server-Sent Events.
        """
        batch_id = str(uuid.uuid4())
        temp_files = []
        
        for data_file in data_files:
            filename = data_file.name.lower()
            suffix = '.xml' if filename.endswith('.xml') else '.yaml'
            
            try:
                with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
                    for chunk in data_file.chunks():
                        f.write(chunk)
                    temp_files.append({
                        'temp_path': f.name,
                        'original_name': data_file.name
                    })
            except Exception as e:
                # Clean up any already-saved files
                for tf in temp_files:
                    if os.path.exists(tf['temp_path']):
                        os.unlink(tf['temp_path'])
                return JsonResponse({
                    'success': False,
                    'batch_id': None,
                    'messages': [{
                        'level': 'error',
                        'text': f'Failed to save file {data_file.name}: {str(e)}'
                    }]
                }, status=500)
        
        # Run duplicate detection on each file for batch preview.
        # Cap detection at 50 files to avoid hammering the GitHub API;
        # files beyond the cap are still processed but skip detection.
        MAX_DETECT = 50
        MAX_DIFF_LINES = 120  # Truncate large diffs in the JSON payload

        preview_files = []
        gh = None
        if len(temp_files) <= MAX_DETECT:
            try:
                from .github_pr_service import GitHubPRService
                gh = GitHubPRService(
                    token=getattr(settings, 'GITHUB_TOKEN', ''),
                    owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                    repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
                )
            except Exception:
                pass

        detection_skipped = len(temp_files) > MAX_DETECT

        for tf in temp_files:
            is_xml = tf['original_name'].lower().endswith('.xml')
            file_info = {
                'filename': tf['original_name'],
                'type': 'xml' if is_xml else 'yaml',
                'duplicate': None,
            }

            if gh:
                try:
                    with open(tf['temp_path'], 'r') as fh:
                        raw_content = fh.read()

                    if is_xml:
                        from pyked.batch_convert import convert_file as _conv
                        chemked_dict = _conv(tf['temp_path'], original_filename=tf['original_name'])
                        check_content = format_chemked_yaml(chemked_dict)
                        check_filename = os.path.splitext(tf['original_name'])[0] + '.yaml'
                    else:
                        check_content = raw_content
                        check_filename = tf['original_name']

                    dup = gh.check_for_duplicates(check_filename, check_content)
                    file_info['repo_folder'] = _repo_folder(
                        gh, check_filename, check_content, dup, allow_api=False,
                    )
                    if dup:
                        classified, truncated, total_lines = _compute_diff(
                            dup['existing_content'], check_content,
                            dup['path'], check_filename,
                            max_lines=MAX_DIFF_LINES,
                        )

                        file_info['duplicate'] = {
                            'match_type': dup['match_type'],
                            'path': dup['path'],
                            'similarity': round(dup['similarity'] * 100),
                            'diff_lines': classified,
                            'has_diff': any(d['kind'] in ('add', 'del') for d in classified),
                            'diff_truncated': truncated,
                            'diff_total_lines': total_lines,
                        }
                except Exception as exc:
                    logger.debug("Batch detection for %s failed: %s", tf['original_name'], exc)

            preview_files.append(file_info)

        # Store batch data in session
        batch_key = f'upload_batch_{batch_id}'
        self.request.session[batch_key] = {
            'temp_files': temp_files,
            'file_format': file_format,
            'validate': validate,
            'file_author': file_author,
            'file_author_orcid': file_author_orcid,
            'contribute_to_github': contribute_to_github,
            'run_pyteck': run_pyteck,
            'github_username': github_username,
            'contribution_description': contribution_description,
        }
        self.request.session.modified = True
        
        # Return batch_id and preview data for client-side review
        return JsonResponse({
            'success': True,
            'batch_id': batch_id,
            'total_files': len(temp_files),
            'sse_url': reverse('chemked_database:dataset-process') + f'?batch_id={batch_id}',
            'preview_files': preview_files,
            'detection_skipped': detection_skipped,
        })
    
    def _process_file_batch(self, data_file, file_format, validate, file_author, file_author_orcid):
        """Process a single file in batch mode (no preview)."""
        filename = data_file.name.lower()
        original_name = data_file.name
        
        # Determine file format
        actual_format = file_format
        if actual_format == 'auto':
            if filename.endswith('.xml'):
                actual_format = 'xml'
            else:
                actual_format = 'yaml'
        
        suffix = '.xml' if actual_format == 'xml' else '.yaml'
        
        # Save uploaded file temporarily
        try:
            with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
                for chunk in data_file.chunks():
                    f.write(chunk)
                temp_path = f.name
        except Exception as e:
            return {'success': False, 'filename': original_name, 'error': str(e)}
        
        try:
            if actual_format == 'xml':
                # Import ReSpecTh XML directly (no preview in batch mode)
                dataset = self._import_respecth_xml_batch(temp_path, original_name, file_author, file_author_orcid)
                return {
                    'success': True,
                    'filename': original_name,
                    'dataset_id': dataset.pk,
                    'dataset_name': dataset.chemked_file_path,
                    'datapoints': dataset.datapoints.count()
                }
            else:
                # Parse ChemKED YAML
                from pyked import chemked
                ck = chemked.ChemKED(yaml_file=temp_path, skip_validation=not validate)
                dataset = self._import_chemked(ck, original_name)
                return {
                    'success': True,
                    'filename': original_name,
                    'dataset_id': dataset.pk,
                    'dataset_name': dataset.chemked_file_path,
                    'datapoints': dataset.datapoints.count()
                }
        except Exception as e:
            logger.exception(f"Error importing file {original_name}")
            formatted = self._format_import_error(str(e))
            return {
                'success': False,
                'filename': original_name,
                'error': formatted['message'],
                'error_kind': formatted['kind']
            }
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _import_respecth_xml_batch(self, temp_path, original_filename, file_author, file_author_orcid):
        """Import ReSpecTh XML in batch mode (no preview)."""
        from pyked.batch_convert import convert_file
        from .chemked_adapter import ChemKEDDictAdapter
        
        chemked_dict = convert_file(temp_path, original_filename=original_filename)
        data = ChemKEDDictAdapter(chemked_dict)
        
        # Log duplicate info but proceed — the GitHub PR will show
        # any differences for the maintainer to review.
        if data.file_doi:
            existing = ExperimentDataset.objects.filter(file_doi=data.file_doi).first()
            if existing:
                log.info(
                    'Dataset with DOI "%s" already exists as "%s" (ID: %s). '
                    'Proceeding — PR will show diff for review.',
                    data.file_doi, existing.chemked_file_path, existing.pk,
                )
        elif data.reference and data.reference.doi:
            similar = ExperimentDataset.objects.filter(
                reference__doi=data.reference.doi
            )
            if data.datapoints:
                similar = similar.annotate(dp_count=Count('datapoints')).filter(
                    dp_count=len(data.datapoints)
                )
            existing = similar.first()
            if existing:
                log.info(
                    'Possible duplicate: reference DOI "%s" with %d datapoints '
                    'matches "%s" (ID: %s). Proceeding — PR will show diff for review.',
                    data.reference.doi, len(data.datapoints),
                    existing.chemked_file_path, existing.pk,
                )
        
        return self._import_from_chemked_dict(chemked_dict, original_filename, file_author)

    def _format_import_error(self, error_msg):
        """Normalize import errors into user-friendly messages."""
        message = str(error_msg or '').strip()
        lower = message.lower()

        if 'skipping duplicate upload' in lower or ('duplicate upload' in lower and 'already exists' in lower):
            clean = message.replace('Skipping duplicate upload.', '').strip()
            if clean:
                return {'kind': 'skipped', 'message': f'Duplicate upload. {clean}'}
            return {'kind': 'skipped', 'message': 'Duplicate upload skipped.'}

        if 'unsupported experiment type' in lower:
            return {
                'kind': 'error',
                'message': f'Unsupported experiment type. {message}'
            }

        if 'value too long for type character varying(100)' in lower:
            return {
                'kind': 'error',
                'message': (
                    'Metadata text is too long for a 100-character field (likely File Author). '
                    'Please shorten the File Author value or contact the admin.'
                )
            }

        if 'chemked_unique_species_per_datapoint' in lower or 'duplicate key value violates unique constraint' in lower:
            return {
                'kind': 'error',
                'message': (
                    'Duplicate species entry in composition. '
                    'The XML file contains the same species listed multiple times in one composition. '
                    'Please check the source file or contact the admin.'
                )
            }

        return {'kind': 'error', 'message': message}
    
    def _process_single_file(self, data_file, file_format, validate, file_author, file_author_orcid, form,
                             contribute_to_github=False, run_pyteck=False,
                             github_username='', contribution_description=''):
        """Process a single file upload — always shows preview first."""
        # Determine file format
        filename = data_file.name.lower()
        if file_format == 'auto':
            if filename.endswith('.xml'):
                file_format = 'xml'
            else:
                file_format = 'yaml'
        
        # Determine suffix based on format
        suffix = '.xml' if file_format == 'xml' else '.yaml'
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
            for chunk in data_file.chunks():
                f.write(chunk)
            temp_path = f.name
        
        try:
            if file_format == 'xml':
                # Try to detect ReSpecTh version
                result = self._import_respecth_xml(
                    temp_path, data_file.name, file_author, file_author_orcid,
                    contribute_to_github=contribute_to_github,
                    run_pyteck=run_pyteck,
                    github_username=github_username,
                    contribution_description=contribution_description,
                )
                return result
            else:
                # ChemKED YAML — show preview before importing
                return self._preview_yaml(
                    temp_path, data_file.name, validate,
                    file_author, file_author_orcid,
                    contribute_to_github=contribute_to_github,
                    run_pyteck=run_pyteck,
                    github_username=github_username,
                    contribution_description=contribution_description,
                )
                    
        except ValueError as e:
            error_msg = str(e)
            # Provide more user-friendly messages for common errors
            if 'preferredKey' in error_msg or 'bibliographyLink' in error_msg:
                messages.error(
                    self.request, 
                    f'ReSpecTh XML Error: The file is missing required bibliography information. '
                    f'Please ensure the <bibliographyLink> element has "preferredKey" and "doi" attributes. '
                    f'Technical details: {error_msg}'
                )
            elif 'experimentType' in error_msg:
                messages.error(
                    self.request,
                    f'ReSpecTh XML Error: Invalid or missing experiment type. '
                    f'Only "Ignition delay measurement" is currently supported. '
                    f'Technical details: {error_msg}'
                )
            else:
                messages.error(self.request, f'Validation error: {error_msg}')
        except NotImplementedError as e:
            messages.error(self.request, f'Not supported: {str(e)}')
        except KeyError as e:
            messages.error(
                self.request, 
                f'Missing required field in file: {str(e)}. '
                f'Please check that all required elements are present in your file.'
            )
        except Exception as e:
            error_msg = str(e)
            logger.exception("Error importing file")
            # Provide context-specific messages for ReSpecTh errors
            if 'preferredKey' in error_msg or 'bibliographyLink' in error_msg:
                messages.error(
                    self.request,
                    f'ReSpecTh XML Error: Missing bibliography reference. '
                    f'The file requires a <bibliographyLink> element with preferredKey and doi attributes. '
                    f'Details: {error_msg}'
                )
            elif 'attribute' in error_msg.lower() and 'missing' in error_msg.lower():
                messages.error(
                    self.request,
                    f'ReSpecTh XML Error: A required XML attribute is missing. {error_msg}'
                )
            else:
                messages.error(self.request, f'Error importing file: {error_msg}')
        finally:
            # Only clean up temp file if we're NOT showing a preview
            # The preview step will clean it up after confirmation/cancellation
            if not self.request.session.get('respecth_preview'):
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        return self.form_invalid(form)

    def _create_contribution_pr(self, data_files, successful_imports,
                                file_author, file_author_orcid,
                                run_pyteck=False, contribution_description='',
                                github_username=''):
        """Create a GitHub PR for the contributed files.

        Parameters
        ----------
        data_files : list[UploadedFile]
            Original uploaded files (Django UploadedFile objects).
        successful_imports : list[dict]
            Import results with 'filename' and 'dataset_name' keys.
        file_author : str
            Contributor display name.
        file_author_orcid : str
            ORCID identifier.
        run_pyteck : bool
            Whether to trigger PyTeCK simulation in CI.
        contribution_description : str
            Optional description for the PR.

        Returns
        -------
        dict or None
            Result with 'pr_url', 'pr_number', 'branch', or None on failure.
        """
        from .github_pr_service import GitHubPRService, GitHubContributionError, verify_orcid, OrcidVerificationError

        # Verify ORCID before creating PR
        if file_author_orcid:
            try:
                orcid_info = verify_orcid(file_author_orcid)
                logger.info(
                    "ORCID %s verified as %s", file_author_orcid, orcid_info["name"]
                )
            except OrcidVerificationError as exc:
                messages.warning(
                    self.request,
                    f'ORCID verification warning: {exc} — PR will still be created.'
                )

        try:
            gh = GitHubPRService(
                token=getattr(settings, 'GITHUB_TOKEN', ''),
                owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
            )
        except GitHubContributionError as exc:
            logger.warning("GitHub PR service not configured: %s", exc)
            messages.warning(
                self.request,
                'GitHub contribution is not configured. Files were imported locally only.'
            )
            return None

        # Build file list for PR: use original uploaded file content
        imported_names = {r['filename'] for r in successful_imports}
        pr_files = []
        for data_file in data_files:
            if data_file.name in imported_names:
                data_file.seek(0)
                content = data_file.read()
                repo_path = gh.determine_repo_path(data_file.name, content)
                pr_files.append({'path': repo_path, 'content': content})

        if not pr_files:
            return None

        # Determine file type
        file_type = 'chemked'
        if any(f['path'].lower().endswith('.xml') for f in pr_files):
            file_type = 'respecth'

        try:
            result = gh.contribute_files(
                files=pr_files,
                contributor_name=file_author or 'Anonymous',
                contributor_orcid=file_author_orcid,
                file_type=file_type,
                description=contribution_description,
                run_pyteck=run_pyteck,
                github_username=github_username,
                validation_passed=True,
            )
            return result
        except GitHubContributionError as exc:
            logger.exception("Failed to create contribution PR")
            messages.warning(
                self.request,
                f'Files imported locally but GitHub PR creation failed: {exc}'
            )
            return None

    def _create_contribution_pr_from_dataset(self, dataset, original_filename,
                                              file_author, file_author_orcid,
                                              run_pyteck=False, contribution_description='',
                                              github_username=''):
        """Create a GitHub PR with ChemKED YAML converted from an imported dataset.

        Used for ReSpecTh XML uploads: the XML is imported into the DB, then
        exported as ChemKED YAML for the PR so that ChemKED-database receives
        the canonical format.
        """
        from .github_pr_service import GitHubPRService, GitHubContributionError, verify_orcid, OrcidVerificationError

        if file_author_orcid:
            try:
                verify_orcid(file_author_orcid)
            except OrcidVerificationError as exc:
                messages.warning(
                    self.request,
                    f'ORCID verification warning: {exc} — PR will still be created.'
                )

        try:
            gh = GitHubPRService(
                token=getattr(settings, 'GITHUB_TOKEN', ''),
                owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
            )
        except GitHubContributionError as exc:
            logger.warning("GitHub PR service not configured: %s", exc)
            messages.warning(
                self.request,
                'GitHub contribution is not configured. Files were imported locally only.'
            )
            return None

        # Convert dataset to ChemKED YAML
        try:
            export_view = DatasetExportView()
            chemked_dict = export_view._dataset_to_chemked_dict(dataset)
            yaml_content = format_chemked_yaml(chemked_dict).encode('utf-8')
        except Exception as exc:
            logger.exception("Failed to convert dataset to ChemKED YAML for PR")
            messages.warning(
                self.request,
                f'Dataset imported locally but YAML conversion for GitHub PR failed: {exc}'
            )
            return None

        # Determine repo path from the YAML content
        yaml_filename = Path(dataset.chemked_file_path).stem + '.yaml'
        repo_path = gh.determine_repo_path(yaml_filename, yaml_content)
        pr_files = [{'path': repo_path, 'content': yaml_content}]

        try:
            result = gh.contribute_files(
                files=pr_files,
                contributor_name=file_author or 'Anonymous',
                contributor_orcid=file_author_orcid,
                file_type='chemked',
                description=contribution_description,
                run_pyteck=run_pyteck,
                github_username=github_username,
                validation_passed=True,
            )
            return result
        except GitHubContributionError as exc:
            logger.exception("Failed to create contribution PR")
            messages.warning(
                self.request,
                f'Files imported locally but GitHub PR creation failed: {exc}'
            )
            return None

    def _create_contribution_pr_from_chemked_dict(self, chemked_dict, dataset_name,
                                                   file_author, file_author_orcid,
                                                   run_pyteck=False, contribution_description='',
                                                   github_username=''):
        """Create a GitHub PR directly from a converter dict (no DB re-export).

        This avoids the round-trip through _dataset_to_chemked_dict which can
        introduce Django enum serialization artifacts (!!python/object/apply).
        """
        from .github_pr_service import GitHubPRService, GitHubContributionError, verify_orcid, OrcidVerificationError

        if file_author_orcid:
            try:
                verify_orcid(file_author_orcid)
            except OrcidVerificationError as exc:
                messages.warning(
                    self.request,
                    f'ORCID verification warning: {exc} — PR will still be created.'
                )

        try:
            gh = GitHubPRService(
                token=getattr(settings, 'GITHUB_TOKEN', ''),
                owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
            )
        except GitHubContributionError as exc:
            logger.warning("GitHub PR service not configured: %s", exc)
            messages.warning(
                self.request,
                'GitHub contribution is not configured. Files were imported locally only.'
            )
            return None

        # Add contributor to file-authors if not already present
        if file_author:
            author_entry = {'name': file_author}
            if file_author_orcid:
                author_entry['ORCID'] = file_author_orcid
            existing = chemked_dict.get('file-authors', [])
            if not any(a.get('name') == file_author for a in existing):
                existing.append(author_entry)
            chemked_dict['file-authors'] = existing

        yaml_content = format_chemked_yaml(chemked_dict).encode('utf-8')

        yaml_filename = Path(dataset_name).stem + '.yaml'
        repo_path = gh.determine_repo_path(yaml_filename, yaml_content)
        pr_files = [{'path': repo_path, 'content': yaml_content}]

        try:
            result = gh.contribute_files(
                files=pr_files,
                contributor_name=file_author or 'Anonymous',
                contributor_orcid=file_author_orcid,
                file_type='chemked',
                description=contribution_description,
                run_pyteck=run_pyteck,
                github_username=github_username,
                validation_passed=True,
            )
            return result
        except GitHubContributionError as exc:
            logger.exception("Failed to create contribution PR")
            messages.warning(
                self.request,
                f'Files imported locally but GitHub PR creation failed: {exc}'
            )
            return None

    def _generate_readable_name(self, data, original_filename, file_type='experiment'):
        """
        Generate a human-readable dataset name following ChemKED database conventions.
        
        Format: {FuelSpecies}/{FirstAuthor}_{Year}_{ApparatusAbbrev}_{ID}.yaml
        
        Examples from ChemKED-database:
        - n-pentane_NOx/Fuller_2021_RCM_1004.yaml
        - n-heptane/Gauthier 2004/st_gauthier_2004-1.yaml
        
        For our flat naming, we use:
        - FuelSpecies_Author_Year_ApparatusAbbrev_ID
        
        Examples:
        - n-pentane_Fuller_2021_RCM_1004
        - n-heptane_Gauthier_2004_ST_1
        """
        import re
        
        parts = []
        
        # 1. Get fuel/parent species from composition
        fuel_species = self._extract_fuel_species(data)
        if fuel_species:
            parts.append(fuel_species)
        elif data.reaction and hasattr(data.reaction, 'preferred_key') and data.reaction.preferred_key:
            # For rate coefficient files, use simplified reaction
            reaction = data.reaction.preferred_key
            # Simplify reaction: "H + O2 = OH + O" -> "H+O2"
            reactants = reaction.split('=')[0].strip() if '=' in reaction else reaction
            species_part = reactants.replace(' + ', '+').replace(' ', '')
            if len(species_part) > 20:
                species_part = species_part[:20]
            parts.append(species_part)
        
        # 2. Get first author's last name
        author_name = None
        if data.reference and data.reference.authors:
            first_author = data.reference.authors[0].name
            # Extract last name (handle "First Last" and "Last, First" formats)
            if ',' in first_author:
                author_name = first_author.split(',')[0].strip()
            else:
                name_parts = first_author.split()
                author_name = name_parts[-1] if name_parts else None
            if author_name:
                # Clean up the last name (keep only alphanumeric)
                author_name = re.sub(r'[^\w]', '', author_name)
                parts.append(author_name)
        
        # 3. Get year
        year = None
        if data.reference and data.reference.year:
            year = str(data.reference.year)
            parts.append(year)
        
        # 4. Get apparatus abbreviation (following ChemKED convention)
        apparatus_abbrev = self._get_apparatus_abbreviation(data)
        if apparatus_abbrev:
            parts.append(apparatus_abbrev)
        
        # 5. Extract ID from original filename
        # e.g., "x00002001.xml" -> "2001", "Fuller_2021_RCM_1004.yaml" -> "1004"
        base_name = os.path.splitext(os.path.basename(original_filename))[0]
        file_id = None
        
        # Try to extract numeric ID from end of filename
        match = re.search(r'(\d+)$', base_name)
        if match:
            file_id = match.group(1).lstrip('0') or '0'  # Remove leading zeros but keep at least one digit
        else:
            # Use last 4 chars as fallback
            file_id = base_name[-4:] if len(base_name) > 4 else base_name
        
        if file_id:
            parts.append(file_id)
        
        # Join with underscores
        if parts:
            readable_name = '_'.join(parts)
        else:
            # Ultimate fallback: use original filename
            readable_name = base_name
        
        # Ensure uniqueness by checking database
        base_readable_name = readable_name
        counter = 1
        while ExperimentDataset.objects.filter(chemked_file_path=readable_name).exists():
            readable_name = f"{base_readable_name}_{counter}"
            counter += 1
        
        return readable_name
    
    def _get_apparatus_abbreviation(self, data):
        """
        Get standard apparatus abbreviation following ChemKED conventions.
        
        Standard abbreviations:
        - ST = Shock Tube
        - RCM = Rapid Compression Machine  
        - JSR = Jet-Stirred Reactor
        - FR = Flow Reactor
        - FL = Flame
        """
        apparatus_kind = None
        
        # Try to get apparatus kind from data
        if hasattr(data, 'apparatus') and data.apparatus:
            if hasattr(data.apparatus, 'kind') and data.apparatus.kind:
                apparatus_kind = data.apparatus.kind
        
        # Also check method field for rate coefficient data
        if not apparatus_kind and hasattr(data, 'method') and data.method:
            apparatus_kind = data.method
        
        if not apparatus_kind:
            return None
        
        kind_lower = apparatus_kind.lower()
        
        # Map to standard abbreviations
        if 'shock' in kind_lower or kind_lower == 'st':
            return 'ST'
        elif 'rcm' in kind_lower or 'rapid compression' in kind_lower:
            return 'RCM'
        elif 'jet' in kind_lower and 'stirred' in kind_lower:
            return 'JSR'
        elif 'stirred' in kind_lower:
            return 'SR'
        elif 'flow' in kind_lower:
            return 'FR'
        elif 'flame' in kind_lower:
            return 'FL'
        elif 'cbs' in kind_lower or 'ab initio' in kind_lower or 'calc' in kind_lower:
            return 'calc'
        else:
            # Return first 3 chars capitalized as fallback
            return re.sub(r'[^\w]', '', apparatus_kind)[:3].upper()
    
    def _extract_fuel_species(self, data):
        """
        Extract primary fuel species from parsed data composition.
        
        Returns the species with highest concentration that is not 
        a common oxidizer/diluent (O2, N2, Ar, He, etc.)
        """
        # Common oxidizers and diluents to exclude
        excluded = {'O2', 'N2', 'Ar', 'He', 'CO2', 'H2O', 'air', 'AR', 'N2O', 'Kr', 'Xe'}
        
        species_list = []
        
        # First, try to get composition from initial_composition (ReSpecTh v2.x format)
        if hasattr(data, 'initial_composition') and data.initial_composition:
            for comp in data.initial_composition:
                sp_name = getattr(comp, 'species_name', None)
                amount = getattr(comp, 'amount', 0)
                if sp_name:
                    species_list.append((sp_name, float(amount) if amount else 0))
        
        # Try to get composition from common_properties
        if not species_list and hasattr(data, 'common_properties') and data.common_properties:
            for prop in data.common_properties:
                if hasattr(prop, 'name') and 'composition' in prop.name.lower():
                    if hasattr(prop, 'species') and prop.species:
                        for sp in prop.species:
                            sp_name = getattr(sp, 'name', None) or getattr(sp, 'species_name', None)
                            amount = getattr(sp, 'amount', 0)
                            if isinstance(amount, (list, tuple)):
                                amount = amount[0] if amount else 0
                            if sp_name:
                                species_list.append((sp_name, float(amount) if amount else 0))
        
        # Try to get composition from datapoints if not in common_properties
        if not species_list and hasattr(data, 'datapoints') and data.datapoints:
            # Get composition from first datapoint
            if data.datapoints:
                dp = data.datapoints[0]
                if hasattr(dp, 'composition') and dp.composition:
                    comp = dp.composition
                    if hasattr(comp, 'species') and comp.species:
                        for sp in comp.species:
                            sp_name = getattr(sp, 'name', None) or getattr(sp, 'species_name', None)
                            amount = getattr(sp, 'amount', 0)
                            if isinstance(amount, (list, tuple)):
                                amount = amount[0] if amount else 0
                            if sp_name:
                                species_list.append((sp_name, float(amount) if amount else 0))
        
        if not species_list:
            return None
        
        # Find the fuel (species with highest concentration not in excluded list)
        fuel = None
        max_amount = -1
        
        for sp_name, amount in species_list:
            # Skip excluded species
            if sp_name.upper() in excluded or sp_name in excluded:
                continue
            if amount > max_amount:
                max_amount = amount
                fuel = sp_name
        
        # If no fuel found (all species excluded), just pick the first non-excluded
        if not fuel:
            for sp_name, _ in species_list:
                if sp_name.upper() not in excluded and sp_name not in excluded:
                    fuel = sp_name
                    break
        
        # Clean up the fuel name (replace special chars with dashes)
        if fuel:
            # Handle common naming patterns
            fuel = fuel.replace(' ', '-')
            # Keep reasonable length
            if len(fuel) > 30:
                fuel = fuel[:30]
        
        return fuel

    def _map_apparatus_kind(self, apparatus_kind, strict=False):
        """Map ReSpecTh apparatus kind text to ApparatusKind enum."""
        if not apparatus_kind:
            return ApparatusKind.SHOCK_TUBE

        kind_lower = apparatus_kind.lower()
        if 'jet' in kind_lower and 'stirred' in kind_lower:
            return ApparatusKind.JET_STIRRED_REACTOR
        if 'stirred' in kind_lower:
            return ApparatusKind.STIRRED_REACTOR
        if 'rcm' in kind_lower or 'rapid compression' in kind_lower:
            return ApparatusKind.RCM
        if 'flow' in kind_lower:
            return ApparatusKind.FLOW_REACTOR
        if 'flame' in kind_lower:
            return ApparatusKind.FLAME
        if 'shock' in kind_lower:
            return ApparatusKind.SHOCK_TUBE

        if strict:
            raise ValueError(
                f'Unsupported apparatus kind "{apparatus_kind}". '
                'Please contact the database maintainer to add support.'
            )
        return ApparatusKind.SHOCK_TUBE

    def _map_experiment_type(self, experiment_type, strict=False):
        """Map ReSpecTh experiment type text to ExperimentType enum."""
        if not experiment_type:
            return ExperimentType.IGNITION_DELAY

        exp_lower = experiment_type.lower()
        if 'jet stirred reactor' in exp_lower or 'jsr' in exp_lower:
            return ExperimentType.JSR_MEASUREMENT
        if 'outlet' in exp_lower and 'concentration' in exp_lower:
            return ExperimentType.OUTLET_CONCENTRATION
        if 'concentration' in exp_lower and 'profile' in exp_lower:
            return ExperimentType.CONCENTRATION_TIME_PROFILE
        if 'ignition' in exp_lower or 'delay' in exp_lower:
            return ExperimentType.IGNITION_DELAY
        if 'flame' in exp_lower or 'speed' in exp_lower or 'burning' in exp_lower or 'velocity' in exp_lower:
            return ExperimentType.LAMINAR_BURNING_VELOCITY
        if 'burner' in exp_lower and 'stabilized' in exp_lower:
            return ExperimentType.BSFS_MEASUREMENT
        if 'species' in exp_lower and 'profile' in exp_lower:
            return ExperimentType.CONCENTRATION_TIME_PROFILE
        if 'rate' in exp_lower or 'coefficient' in exp_lower:
            return ExperimentType.RATE_COEFFICIENT
        if 'thermo' in exp_lower:
            return ExperimentType.THERMOCHEMICAL

        if strict:
            raise ValueError(
                f'Unsupported experiment type "{experiment_type}". '
                'Please contact the database maintainer to add support.'
            )
        return ExperimentType.IGNITION_DELAY

    def _preview_yaml(self, temp_path, original_filename, validate,
                      file_author, file_author_orcid,
                      contribute_to_github=False, run_pyteck=False,
                      github_username='', contribution_description=''):
        """Show a preview for ChemKED YAML files before importing.

        Parses the YAML to extract metadata, runs duplicate detection,
        and stores state in the session so the confirm step can
        proceed identically to the ReSpecTh preview flow.
        """
        try:
            with open(temp_path, 'r') as fh:
                raw_content = fh.read()
            data = yaml.safe_load(raw_content)
            if not isinstance(data, dict):
                raise ValueError('File does not contain a valid YAML mapping')

            # Extract metadata for preview display
            ref = data.get('reference', {}) or {}
            exp_type = data.get('experiment-type', '')
            apparatus = data.get('apparatus', {}) or {}
            dps = data.get('datapoints', []) or []

            # Try to build a readable suggested name
            reaction_str = data.get('reaction', '')
            ref_authors = ref.get('authors', [])
            ref_authors_str = ', '.join(a.get('name', '') for a in ref_authors) if ref_authors else ''

            suggested_name = os.path.splitext(original_filename)[0]
            # Attempt same naming logic as XML path
            try:
                from .chemked_adapter import ChemKEDDictAdapter
                adapter = ChemKEDDictAdapter(data)
                suggested_name = self._generate_readable_name(adapter, original_filename, 'experiment')
            except Exception:
                pass

            preview_info = {
                'dataset_name': suggested_name,
                'original_filename': original_filename,
                'temp_file_path': temp_path,
                'file_type': 'yaml',
                'file_author': file_author or '',
                'datapoints_count': len(dps),
                'reference_doi': ref.get('doi', ''),
                'reference_journal': ref.get('journal', ''),
                'reference_year': ref.get('year', ''),
                'reference_authors': ref_authors_str,
                'reaction': reaction_str,
                'experiment_type': exp_type,
                'validation_error': None,
                'can_confirm': True,
                'contribute_to_github': contribute_to_github,
                'run_pyteck': run_pyteck,
                'github_username': github_username,
                'contribution_description': contribution_description,
                'file_author_orcid': file_author_orcid,
            }

            # --- Duplicate detection against ChemKED-database repo --------
            try:
                from .github_pr_service import GitHubPRService, GitHubContributionError
                gh = GitHubPRService(
                    token=getattr(settings, 'GITHUB_TOKEN', ''),
                    owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                    repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
                )
                yaml_filename = os.path.splitext(original_filename)[0] + '.yaml'
                dup = gh.check_for_duplicates(yaml_filename, raw_content)
                preview_info['repo_folder'] = _repo_folder(gh, yaml_filename, raw_content, dup)
                if dup:
                    classified, _, _ = _compute_diff(
                        dup['existing_content'], raw_content,
                        dup['path'], yaml_filename,
                    )
                    preview_info['duplicate_match'] = {
                        'match_type': dup['match_type'],
                        'path': dup['path'],
                        'similarity': round(dup['similarity'] * 100),
                        'diff_lines': classified,
                        'has_diff': any(d['kind'] in ('add', 'del') for d in classified),
                    }
            except Exception as exc:
                logger.debug("Duplicate detection skipped: %s", exc)

            self.request.session['respecth_preview'] = preview_info
            return redirect(f"{self.request.path}?preview=1")

        except Exception as e:
            logger.exception("Error parsing ChemKED YAML file")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            messages.error(self.request, f'Error parsing YAML file: {e}')
            return self.form_invalid(self.get_form())

    def _import_respecth_xml(self, temp_path, original_filename, file_author, file_author_orcid,
                              contribute_to_github=False, run_pyteck=False,
                              github_username='', contribution_description=''):
        """
        Import ReSpecTh XML file. Tries v2.x format first, falls back to v1.x via PyKED.
        """
        import xml.etree.ElementTree as ET
        
        # First, detect the ReSpecTh version by checking the root element
        try:
            tree = ET.parse(temp_path)
            root = tree.getroot()
            root_tag = root.tag
        except ET.ParseError as e:
            messages.error(self.request, f'Invalid XML file: {str(e)}')
            return self.form_invalid(self.get_form())
        
        # Check if it's a ReSpecTh v2.x file (kdetermination, tdetermination, etc.)
        v2_root_tags = ['kdetermination', 'tdetermination', 'experiment']
        
        if root_tag in v2_root_tags:
            # Use our ReSpecTh v2 converter
            return self._import_respecth_v2(
                temp_path, original_filename, root_tag, file_author,
                file_author_orcid=file_author_orcid,
                contribute_to_github=contribute_to_github,
                run_pyteck=run_pyteck,
                github_username=github_username,
                contribution_description=contribution_description,
            )
        else:
            # Try PyKED's converter for v1.x format
            return self._import_respecth_v1(temp_path, original_filename, file_author, file_author_orcid)
    
    def _import_respecth_v2(self, temp_path, original_filename, file_type, file_author,
                             file_author_orcid='', contribute_to_github=False,
                             run_pyteck=False, github_username='',
                             contribution_description=''):
        """
        Import ReSpecTh v2.x format file (kdetermination, tdetermination, etc.).
        Shows a preview step first so user can edit the dataset name.
        """
        from pyked.batch_convert import convert_file
        from .chemked_adapter import ChemKEDDictAdapter
        
        try:
            chemked_dict = convert_file(temp_path, original_filename=original_filename)
            data = ChemKEDDictAdapter(chemked_dict)

            validation_error = None
            if data.file_type == 'experiment':
                # Validate experiment type early so users get clear feedback
                try:
                    self._map_experiment_type(data.experiment_type, strict=True)
                except ValueError as exc:
                    validation_error = str(exc)
            
            # Generate suggested name
            suggested_name = self._generate_readable_name(data, original_filename, data.file_type)
            
            # Build preview info
            ref = data.reference
            _ue = html_mod.unescape  # XML entities like &amp; → &
            preview_info = {
                'dataset_name': suggested_name,
                'original_filename': original_filename,
                'temp_file_path': temp_path,
                'file_type': data.file_type,
                'file_author': file_author or data.file_author or '',
                'datapoints_count': len(data.datapoints),
                'reference_doi': ref.doi if ref else '',
                'reference_journal': _ue(ref.journal) if ref else '',
                'reference_year': ref.year if ref else '',
                'reference_authors': _ue(', '.join([a.name for a in ref.authors])) if ref and ref.authors else '',
                'reaction': _ue(' / '.join(rxn.preferred_key for rxn in data.reactions)) if data.reactions else '',
                'experiment_type': data.experiment_type or data.file_type,
                'validation_error': validation_error,
                'can_confirm': validation_error is None,
                'supported_experiment_types': [choice.label for choice in ExperimentType],
                'contribute_to_github': contribute_to_github,
                'run_pyteck': run_pyteck,
                'github_username': github_username,
                'contribution_description': contribution_description,
                'file_author_orcid': file_author_orcid,
            }

            # --- Duplicate detection against ChemKED-database repo --------
            # Generate the YAML that would be contributed so we can compare.
            try:
                yaml_content = format_chemked_yaml(chemked_dict)
                yaml_filename = os.path.splitext(original_filename)[0] + '.yaml'

                from .github_pr_service import GitHubPRService, GitHubContributionError
                gh = GitHubPRService(
                    token=getattr(settings, 'GITHUB_TOKEN', ''),
                    owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                    repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
                )
                dup = gh.check_for_duplicates(yaml_filename, yaml_content)
                preview_info['repo_folder'] = _repo_folder(gh, yaml_filename, yaml_content, dup)
                if dup:
                    classified, _, _ = _compute_diff(
                        dup['existing_content'], yaml_content,
                        dup['path'], yaml_filename,
                    )

                    preview_info['duplicate_match'] = {
                        'match_type': dup['match_type'],
                        'path': dup['path'],
                        'similarity': round(dup['similarity'] * 100),
                        'diff_lines': classified,
                        'has_diff': any(d['kind'] in ('add', 'del') for d in classified),
                    }
            except (GitHubContributionError, Exception) as exc:
                # Non-fatal: detection failing shouldn't block the preview
                logger.debug("Duplicate detection skipped: %s", exc)

            # Store in session for preview
            self.request.session['respecth_preview'] = preview_info
            
            # Redirect to preview
            return redirect(f"{self.request.path}?preview=1")
            
        except Exception as e:
            logger.exception("Error parsing ReSpecTh v2 file")
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            messages.error(
                self.request,
                f'Error parsing ReSpecTh v2 file: {str(e)}'
            )
            return self.form_invalid(self.get_form())
            messages.error(
                self.request,
                f'Error importing ReSpecTh v2 file: {str(e)}'
            )
            return self.form_invalid(self.get_form())
    
    def _import_respecth_v1(self, temp_path, original_filename, file_author, file_author_orcid):
        """Import ReSpecTh v1.x format file using PyKED."""
        try:
            from pyked import chemked
            
            ck = chemked.ChemKED.from_respecth(
                temp_path,
                file_author=file_author,
                file_author_orcid=file_author_orcid
            )
            
            dataset = self._import_chemked(ck, original_filename)
            
            messages.success(
                self.request,
                f'Successfully imported ReSpecTh v1 XML "{original_filename}" with {dataset.datapoints.count()} datapoints.'
            )
            return redirect('chemked_database:dataset-detail', pk=dataset.pk)
            
        except ImportError:
            messages.error(self.request, 'PyKED is not installed. Cannot import ReSpecTh v1.x files.')
        except Exception as e:
            error_msg = str(e)
            logger.exception("Error importing ReSpecTh v1 file")
            if 'preferredKey' in error_msg or 'bibliographyLink' in error_msg:
                messages.error(
                    self.request,
                    f'This appears to be a ReSpecTh v2.x file but was not recognized. '
                    f'Please check the file format. Details: {error_msg}'
                )
            else:
                messages.error(self.request, f'Error importing ReSpecTh file: {error_msg}')
        
        return self.form_invalid(self.get_form())
    
    # ------------------------------------------------------------------
    # Unified import from ChemKED dict (output of batch_convert)
    # ------------------------------------------------------------------
    
    @transaction.atomic
    def _import_from_chemked_dict(self, chemked_dict, original_filename, file_author, custom_name=None):
        """Import a ChemKED dict (from batch_convert.convert_file) into the database.
        
        Handles experiment, kdetermination, and tdetermination file types.
        """
        from .chemked_adapter import ChemKEDDictAdapter, _parse_chemked_value
        
        data = ChemKEDDictAdapter(chemked_dict)
        file_type = data.file_type
        
        # Generate dataset name
        if custom_name:
            readable_name = custom_name
        else:
            readable_name = self._generate_readable_name(data, original_filename, file_type)
        
        # Map experiment type
        exp_type_str = data.experiment_type
        if file_type == 'kdetermination':
            exp_type = ExperimentType.RATE_COEFFICIENT
        elif file_type == 'tdetermination':
            exp_type = ExperimentType.THERMOCHEMICAL
        else:
            exp_type = self._map_experiment_type(exp_type_str, strict=True)
        
        # Apparatus
        apparatus_kind_str = data.apparatus_kind or (data.method if file_type == 'kdetermination' else '')
        apparatus_kind = self._map_apparatus_kind(apparatus_kind_str)
        apparatus, _ = Apparatus.objects.get_or_create(
            kind=apparatus_kind, institution='', facility='',
        )
        
        # Reference
        ref = data.reference
        ref_doi = ref.doi if ref else ''
        ref_journal = ref.journal if ref else ''
        ref_year = ref.year if ref else None
        ref_volume = None
        if ref and ref.volume:
            try:
                ref_volume = int(ref.volume)
            except (ValueError, TypeError):
                pass
        ref_pages = ref.pages if ref else ''
        ref_detail = ref.location if ref else ''
        ref_title = ref.title if ref else ''
        ref_table = ref.table if ref else ''
        ref_figure = ref.figure if ref else ''
        ref_location = ref.location if ref else ''
        
        # Dates
        first_pub_date = None
        last_mod_date = None
        if data.first_publication_date:
            try:
                from datetime import datetime
                first_pub_date = datetime.strptime(data.first_publication_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        if data.last_modification_date:
            try:
                from datetime import datetime
                last_mod_date = datetime.strptime(data.last_modification_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Create or update dataset (allow re-upload of existing files)
        dataset, created = ExperimentDataset.objects.update_or_create(
            chemked_file_path=readable_name,
            defaults=dict(
                experiment_type=exp_type,
                apparatus=apparatus,
                chemked_version='0.4.1',
                file_version=0,
                reference_doi=ref_doi or '',
                reference_journal=ref_journal or '',
                reference_year=ref_year,
                reference_volume=ref_volume,
                reference_pages=ref_pages or '',
                reference_detail=ref_detail or '',
                reference_title=ref_title or '',
                reference_table=ref_table or '',
                reference_figure=ref_figure or '',
                reference_location=ref_location or '',
                file_doi=data.file_doi or '',
                respecth_version=data.respecth_version or '',
                first_publication_date=first_pub_date,
                last_modification_date=last_mod_date,
                method=data.method or '',
                comments=data.comments or [],
            ),
        )
        
        # If updating, clear old related objects so they get re-created
        if not created:
            dataset.datapoints.all().delete()
            dataset.file_authors.clear()
            dataset.reference_authors.clear()
            if hasattr(dataset, 'common_properties') and dataset.common_properties:
                dataset.common_properties.delete()
        
        # Add authors
        if ref and ref.authors:
            for author_data in ref.authors:
                author, _ = ReferenceAuthor.objects.get_or_create(
                    name=author_data.name,
                    defaults={'orcid': author_data.orcid or ''}
                )
                dataset.reference_authors.add(author)
        
        if file_author or data.file_author:
            author_name = file_author or data.file_author
            fa, _ = FileAuthor.objects.get_or_create(
                name=author_name, defaults={'orcid': ''},
            )
            dataset.file_authors.add(fa)
        
        # Store reaction info for kdetermination
        if data.reactions:
            reaction_lines = [f"Reaction: {rxn.preferred_key}" for rxn in data.reactions]
            reaction_info = '\n'.join(reaction_lines)
            if dataset.reference_detail:
                dataset.reference_detail += f"\n{reaction_info}"
            else:
                dataset.reference_detail = reaction_info
            dataset.save()
        
        # Dispatch to type-specific datapoint import
        raw = chemked_dict
        if file_type == 'kdetermination':
            self._import_kdet_datapoints(raw, dataset, data, _parse_chemked_value)
        elif file_type == 'tdetermination':
            self._import_tdet_datapoints(raw, dataset, _parse_chemked_value)
        else:
            self._import_experiment_datapoints(raw, dataset, data, _parse_chemked_value)
        
        return dataset
    
    def _import_experiment_datapoints(self, raw, dataset, data, _parse_chemked_value):
        """Import datapoints for experiment files from ChemKED dict."""
        common = raw.get('common-properties') or {}

        def _extract_meta_value(value):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                match = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", value)
                return float(match.group(1)) if match else None
            return None

        def _normalize_quantity_meta(meta):
            if not meta:
                return {}

            return {
                'uncertainty_type': meta.get('uncertainty-type', ''),
                'uncertainty': _extract_meta_value(meta.get('uncertainty')),
                'upper_uncertainty': _extract_meta_value(meta.get('upper-uncertainty')),
                'lower_uncertainty': _extract_meta_value(meta.get('lower-uncertainty')),
                'evaluated_standard_deviation': _extract_meta_value(meta.get('evaluated-standard-deviation')),
                'evaluated_standard_deviation_type': meta.get('evaluated-standard-deviation-type', ''),
                'evaluated_standard_deviation_sourcetype': meta.get('evaluated-standard-deviation-sourcetype', ''),
                'evaluated_standard_deviation_method': meta.get('evaluated-standard-deviation-method', ''),
            }

        def _merge_uncertainty_meta(meta, uncertainty, upper, lower, unc_type):
            merged = dict(meta or {})
            if uncertainty is not None and 'uncertainty' not in merged:
                merged['uncertainty'] = uncertainty
            if upper is not None and 'upper-uncertainty' not in merged:
                merged['upper-uncertainty'] = upper
            if lower is not None and 'lower-uncertainty' not in merged:
                merged['lower-uncertainty'] = lower
            if unc_type and 'uncertainty-type' not in merged:
                merged['uncertainty-type'] = unc_type
            return merged

        def _create_quantity(value, units, meta=None):
            normalized = _normalize_quantity_meta(meta)
            if value is None and not normalized:
                return None

            return ValueWithUnit.objects.create(
                value=value,
                units=units or '',
                uncertainty_type=normalized.get('uncertainty_type', ''),
                uncertainty=normalized.get('uncertainty'),
                upper_uncertainty=normalized.get('upper_uncertainty'),
                lower_uncertainty=normalized.get('lower_uncertainty'),
                evaluated_standard_deviation=normalized.get('evaluated_standard_deviation'),
                evaluated_standard_deviation_type=normalized.get('evaluated_standard_deviation_type', ''),
                evaluated_standard_deviation_sourcetype=normalized.get('evaluated_standard_deviation_sourcetype', ''),
                evaluated_standard_deviation_method=normalized.get('evaluated_standard_deviation_method', ''),
            )
        
        # Import initial composition
        common_composition = self._import_composition_from_chemked(common.get('composition'))
        
        # Extract common scalar values
        common_pressure = None
        common_temperature = None
        common_equiv_ratio = None
        common_volume = None
        common_residence_time = None
        common_quantities = {}
        
        for key in ('pressure', 'temperature', 'equivalence-ratio', 'reactor-volume',
                     'residence-time', 'volume'):
            val_raw = common.get(key)
            if val_raw is None:
                continue
            val, units, _unc = _parse_chemked_value(val_raw)
            if val is None:
                continue
            common_quantities[key] = _create_quantity(val, units, _unc)
            if key == 'pressure':
                common_pressure = self._convert_to_si(val, units, 'pressure')
            elif key == 'temperature':
                common_temperature = self._convert_to_si(val, units, 'temperature')
            elif key == 'equivalence-ratio':
                common_equiv_ratio = val
            elif key in ('reactor-volume', 'volume'):
                common_volume = self._convert_volume_to_si(val, units)
            elif key == 'residence-time':
                common_residence_time = self._convert_to_si(val, units, 'time')
        
        # Build global uncertainty map from common-properties inline uncertainty
        global_unc = {}
        for key, val_raw in common.items():
            if key in ('composition', 'ignition-type', '_pending_esd'):
                continue
            if isinstance(val_raw, list) and len(val_raw) > 1 and isinstance(val_raw[1], dict):
                unc_dict = val_raw[1]
                ref_name = key.replace('-', ' ')
                unc_type = unc_dict.get('uncertainty-type', 'absolute')
                
                def _extract_unc_val(v):
                    if v is None:
                        return None
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str):
                        m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", v)
                        return float(m.group(1)) if m else None
                    return None
                
                sym = _extract_unc_val(unc_dict.get('uncertainty'))
                upper = _extract_unc_val(unc_dict.get('upper-uncertainty'))
                lower = _extract_unc_val(unc_dict.get('lower-uncertainty'))
                
                if sym is not None or upper is not None or lower is not None:
                    global_unc[ref_name] = {
                        'uncertainty': sym, 'upper_uncertainty': upper,
                        'lower_uncertainty': lower, 'type': unc_type,
                    }
        
        # Create common properties record
        if common_pressure is not None or common_equiv_ratio is not None or common_composition or common_volume is not None or common_residence_time is not None:
            CommonProperties.objects.create(
                dataset=dataset,
                pressure=common_pressure,
                pressure_quantity=common_quantities.get('pressure'),
                composition=common_composition,
                equivalence_ratio=common_equiv_ratio,
                equivalence_ratio_quantity=common_quantities.get('equivalence-ratio'),
                # The numbers are converted to SI above; the quantities keep the file's units.
                reactor_volume=common_volume,
                reactor_volume_units='m3' if common_volume is not None else '',
                reactor_volume_quantity=common_quantities.get('reactor-volume') or common_quantities.get('volume'),
                residence_time=common_residence_time,
                residence_time_units='s' if common_residence_time is not None else '',
                residence_time_quantity=common_quantities.get('residence-time'),
                temperature=common_temperature,
                temperature_quantity=common_quantities.get('temperature'),
            )
        
        # Build composition uncertainty/ESD maps from common composition species
        comp_unc_map = {}
        esd_map = {}
        comp_block = common.get('composition') or {}
        for sp in comp_block.get('species', []):
            sp_name = sp.get('species-name', '')
            amount_list = sp.get('amount') or []
            if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                meta = amount_list[1]
                unc_val = meta.get('uncertainty')
                if unc_val is not None:
                    if isinstance(unc_val, str):
                        m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", unc_val)
                        unc_val = float(m.group(1)) if m else None
                    elif isinstance(unc_val, (int, float)):
                        unc_val = float(unc_val)
                    if unc_val is not None:
                        comp_unc_map[sp_name] = {
                            'value': unc_val,
                            'kind': meta.get('uncertainty-type', 'absolute'),
                            'source_type': meta.get('uncertainty-sourcetype', ''),
                        }
                esd_val = meta.get('evaluated-standard-deviation')
                if esd_val is not None:
                    if isinstance(esd_val, (int, float)):
                        esd_val = float(esd_val)
                    esd_map[sp_name] = {
                        'value': esd_val,
                        'kind': meta.get('evaluated-standard-deviation-type', 'absolute'),
                        'source_type': meta.get('evaluated-standard-deviation-sourcetype', ''),
                        'method': meta.get('evaluated-standard-deviation-method', ''),
                    }
        
        def _resolve_unc(dp_unc, reference):
            ref = reference.lower()
            unc = dp_unc.get(ref) or global_unc.get(ref)
            if unc:
                return unc['uncertainty'], unc['upper_uncertainty'], unc['lower_uncertainty'], unc['type']
            return None, None, None, ''
        
        # Import datapoints
        for dp in raw.get('datapoints', []):
            temp_val, temp_units, temp_unc_dict = _parse_chemked_value(dp.get('temperature'))
            pres_val, pres_units, pres_unc_dict = _parse_chemked_value(dp.get('pressure'))
            ign_val, ign_units, ign_unc_dict = _parse_chemked_value(dp.get('ignition-delay'))
            lbv_val, lbv_units, lbv_unc_dict = _parse_chemked_value(dp.get('laminar-burning-velocity'))
            res_val, res_units, _res_unc = _parse_chemked_value(dp.get('residence-time'))
            equiv_val, _eu, _eunc = _parse_chemked_value(dp.get('equivalence-ratio'))
            
            # Build per-datapoint uncertainty from inline dicts
            dp_uncertainties = {}
            for prop_key, unc_d in [('temperature', temp_unc_dict), ('pressure', pres_unc_dict),
                                     ('ignition delay', ign_unc_dict),
                                     ('laminar burning velocity', lbv_unc_dict)]:
                if unc_d:
                    unc_type = unc_d.get('uncertainty-type', 'absolute')
                    
                    def _ext(v):
                        if v is None:
                            return None
                        if isinstance(v, (int, float)):
                            return float(v)
                        if isinstance(v, str):
                            m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", v)
                            return float(m.group(1)) if m else None
                        return None
                    
                    dp_uncertainties[prop_key] = {
                        'uncertainty': _ext(unc_d.get('uncertainty')),
                        'upper_uncertainty': _ext(unc_d.get('upper-uncertainty')),
                        'lower_uncertainty': _ext(unc_d.get('lower-uncertainty')),
                        'type': unc_type,
                    }
            
            # Convert to SI
            temp_si = self._convert_to_si(temp_val, temp_units, 'temperature') if temp_val else (common_temperature or 0)
            pres_si = self._convert_to_si(pres_val, pres_units, 'pressure') if pres_val else (common_pressure or 0)
            res_si = self._convert_to_si(res_val, res_units, 'time') if res_val else None
            
            # Resolve uncertainties
            temp_unc, temp_upper, temp_lower, temp_unc_type = _resolve_unc(dp_uncertainties, 'temperature')
            press_unc, press_upper, press_lower, press_unc_type = _resolve_unc(dp_uncertainties, 'pressure')
            temp_quantity = _create_quantity(
                temp_val,
                temp_units,
                _merge_uncertainty_meta(temp_unc_dict, temp_unc, temp_upper, temp_lower, temp_unc_type),
            )
            pressure_quantity = _create_quantity(
                pres_val,
                pres_units,
                _merge_uncertainty_meta(pres_unc_dict, press_unc, press_upper, press_lower, press_unc_type),
            )
            
            datapoint = ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=temp_si,
                temperature_quantity=temp_quantity,
                pressure=pres_si,
                pressure_quantity=pressure_quantity,
                equivalence_ratio=equiv_val or common_equiv_ratio,
                equivalence_ratio_quantity=_create_quantity(equiv_val, _eu, _eunc),
                residence_time=res_si,
                residence_time_units='s' if res_si else '',
            )
            
            # Ignition delay
            if ign_val is not None:
                ign_si = self._convert_to_si(ign_val, ign_units, 'time')
                ign_unc, ign_upper, ign_lower, ign_unc_type = _resolve_unc(dp_uncertainties, 'ignition delay')
                ign_quantity = _create_quantity(
                    ign_val,
                    ign_units,
                    _merge_uncertainty_meta(ign_unc_dict, ign_unc, ign_upper, ign_lower, ign_unc_type),
                )
                IgnitionDelayDatapoint.objects.create(
                    datapoint=datapoint,
                    ignition_delay=ign_si,
                    ignition_delay_quantity=ign_quantity,
                )
            
            # Laminar burning velocity
            if lbv_val is not None:
                lbv_si = self._convert_to_si(lbv_val, lbv_units, 'velocity')
                lbv_unc, lbv_upper, lbv_lower, lbv_unc_type = _resolve_unc(dp_uncertainties, 'laminar burning velocity')
                lbv_quantity = _create_quantity(
                    lbv_val,
                    lbv_units,
                    _merge_uncertainty_meta(lbv_unc_dict, lbv_unc, lbv_upper, lbv_lower, lbv_unc_type),
                )
                LaminarBurningVelocityMeasurementDatapoint.objects.create(
                    datapoint=datapoint,
                    laminar_burning_velocity=lbv_si,
                    laminar_burning_velocity_quantity=lbv_quantity,
                )
            
            # Per-datapoint composition (measured species concentrations)
            dp_comp = dp.get('composition') or dp.get('measured-composition')
            if dp_comp and isinstance(dp_comp, dict) and dp_comp.get('species'):
                dp_composition = self._import_composition_from_chemked(
                    dp_comp, comp_unc_map=comp_unc_map, esd_map=esd_map
                )
                if dp_composition:
                    datapoint.composition = dp_composition
                    datapoint.save()
    
    def _import_kdet_datapoints(self, raw, dataset, data, _parse_chemked_value):
        """Import datapoints for kdetermination files from ChemKED dict."""
        common = raw.get('common-properties') or {}
        
        # Extract evaluated standard deviation from common properties
        common_eval_std_dev = None
        common_eval_std_dev_type = ''
        common_eval_std_dev_sourcetype = ''
        
        for key, val_raw in common.items():
            if isinstance(val_raw, list) and len(val_raw) > 1 and isinstance(val_raw[1], dict):
                meta = val_raw[1]
                esd = meta.get('evaluated-standard-deviation')
                if esd is not None:
                    common_eval_std_dev = float(esd) if isinstance(esd, (int, float)) else None
                    common_eval_std_dev_type = meta.get('evaluated-standard-deviation-type', 'absolute')
                    common_eval_std_dev_sourcetype = meta.get('evaluated-standard-deviation-sourcetype', '')
        
        # Also check for top-level ESD in common that isn't inline on a property
        # (e.g., standalone ESD for rate coefficient)
        for key, val_raw in common.items():
            if key in ('composition', 'ignition-type', '_pending_esd'):
                continue
            if isinstance(val_raw, list) and len(val_raw) > 1 and isinstance(val_raw[1], dict):
                meta = val_raw[1]
                esd = meta.get('evaluated-standard-deviation')
                if esd is not None and common_eval_std_dev is None:
                    if isinstance(esd, str):
                        m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", esd)
                        common_eval_std_dev = float(m.group(1)) if m else None
                    else:
                        common_eval_std_dev = float(esd)
                    common_eval_std_dev_type = meta.get('evaluated-standard-deviation-type', 'absolute')
                    common_eval_std_dev_sourcetype = meta.get('evaluated-standard-deviation-sourcetype', '')
        
        # Common pressure
        common_pressure_si = None
        pval, punits, _punc = _parse_chemked_value(common.get('pressure'))
        if pval is not None:
            common_pressure_si = self._convert_to_si(pval, punits, 'pressure')
        
        # Reaction info
        reaction_str = ' / '.join(rxn.preferred_key for rxn in data.reactions) if data.reactions else ''
        reaction_order = data.reaction.order if data.reaction else None
        bulk_gas = ', '.join(filter(None, (rxn.bulk_gas for rxn in data.reactions))) if data.reactions else ''
        method_str = data.method or ''
        
        for dp in raw.get('datapoints', []):
            temp_val, temp_units, _tunc = _parse_chemked_value(dp.get('temperature'))
            pres_val, pres_units, _punc = _parse_chemked_value(dp.get('pressure'))
            rc_val, rc_units, rc_unc_dict = _parse_chemked_value(dp.get('rate-coefficient'))
            br_val, br_units, br_unc_dict = _parse_chemked_value(dp.get('branching-ratio'))
            
            # Determine measurement type and values
            if br_val is not None:
                meas_val, meas_units, meas_unc_dict = br_val, br_units or 'unitless', br_unc_dict
                measurement_type = MeasurementType.BRANCHING_RATIO
            elif rc_val is not None:
                meas_val, meas_units, meas_unc_dict = rc_val, rc_units or 'cm3 mol-1 s-1', rc_unc_dict
                measurement_type = MeasurementType.RATE_COEFFICIENT
            else:
                continue
            
            # Parse inline uncertainty
            rc_uncertainty = None
            rc_upper = None
            rc_lower = None
            rc_unc_type = ''
            dp_eval_std_dev = None
            dp_eval_std_dev_type = ''
            dp_eval_std_dev_sourcetype = ''
            
            if meas_unc_dict:
                rc_unc_type = meas_unc_dict.get('uncertainty-type', 'absolute')
                
                def _ext(v):
                    if v is None:
                        return None
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str):
                        m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", v)
                        return float(m.group(1)) if m else None
                    return None
                
                rc_uncertainty = _ext(meas_unc_dict.get('uncertainty'))
                rc_upper = _ext(meas_unc_dict.get('upper-uncertainty'))
                rc_lower = _ext(meas_unc_dict.get('lower-uncertainty'))
                
                # Per-datapoint ESD from inline dict
                esd_raw = meas_unc_dict.get('evaluated-standard-deviation')
                if esd_raw is not None:
                    dp_eval_std_dev = _ext(esd_raw)
                    dp_eval_std_dev_type = meas_unc_dict.get('evaluated-standard-deviation-type', 'absolute')
                    dp_eval_std_dev_sourcetype = meas_unc_dict.get('evaluated-standard-deviation-sourcetype', '')
            
            # Convert temperature/pressure to SI
            temp_si = self._convert_to_si(temp_val, temp_units, 'temperature') if temp_val else 0
            if pres_val is not None:
                pressure_si = self._convert_to_si(pres_val, pres_units, 'pressure')
            else:
                pressure_si = common_pressure_si
            
            # Create ValueWithUnit for rate coefficient
            eff_esd = dp_eval_std_dev if dp_eval_std_dev is not None else common_eval_std_dev
            eff_esd_type = dp_eval_std_dev_type or common_eval_std_dev_type
            eff_esd_sourcetype = dp_eval_std_dev_sourcetype or common_eval_std_dev_sourcetype
            
            rc_vu = ValueWithUnit.objects.create(
                value=meas_val,
                units=meas_units,
                uncertainty=rc_uncertainty,
                upper_uncertainty=rc_upper,
                lower_uncertainty=rc_lower,
                uncertainty_type=rc_unc_type,
                evaluated_standard_deviation=eff_esd,
                evaluated_standard_deviation_type=eff_esd_type,
                evaluated_standard_deviation_sourcetype=eff_esd_sourcetype,
            )
            
            # Create temperature ValueWithUnit
            temp_vu = None
            if temp_val is not None:
                temp_vu = ValueWithUnit.objects.create(value=temp_val, units=temp_units or 'K')
            
            # Create pressure ValueWithUnit
            pressure_vu = None
            if pres_val is not None:
                pressure_vu = ValueWithUnit.objects.create(value=pres_val, units=pres_units or 'atm')
            
            datapoint = ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=temp_si,
                temperature_quantity=temp_vu,
                pressure=pressure_si or 0,
                pressure_quantity=pressure_vu,
            )
            
            RateCoefficientDatapoint.objects.create(
                datapoint=datapoint,
                measurement_type=measurement_type,
                rate_coefficient=meas_val,
                rate_coefficient_units=meas_units,
                rate_coefficient_quantity=rc_vu,
                reaction=reaction_str,
                reaction_order=reaction_order,
                bulk_gas=bulk_gas,
                method=method_str,
            )
    
    def _import_tdet_datapoints(self, raw, dataset, _parse_chemked_value):
        """Import datapoints for tdetermination files from ChemKED dict."""
        for dp in raw.get('datapoints', []):
            temp_val, temp_units, _tunc = _parse_chemked_value(dp.get('temperature'))
            temp_si = self._convert_to_si(temp_val, temp_units, 'temperature') if temp_val else 0
            
            ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=temp_si,
                pressure=0,
            )
    
    def _import_composition_from_chemked(self, comp_data, comp_unc_map=None, esd_map=None):
        """Import a ChemKED composition block into a Composition model."""
        if not comp_data or not isinstance(comp_data, dict):
            return None
        
        species_list = comp_data.get('species') or []
        if not species_list:
            return None
        
        kind_str = comp_data.get('kind', 'mole fraction')
        kind_map = {
            'mole fraction': CompositionKind.MOLE_FRACTION,
            'mass fraction': CompositionKind.MASS_FRACTION,
            'mole percent': CompositionKind.MOLE_PERCENT,
        }
        comp_kind = kind_map.get(kind_str, CompositionKind.MOLE_FRACTION)
        
        composition = Composition.objects.create(kind=comp_kind)
        
        for sp in species_list:
            sp_name = sp.get('species-name', '')
            amount_list = sp.get('amount') or []
            amount_val = 0.0
            if isinstance(amount_list, list) and amount_list:
                try:
                    amount_val = float(amount_list[0])
                except (ValueError, TypeError):
                    pass
            elif isinstance(amount_list, (int, float)):
                amount_val = float(amount_list)
            
            # Species uncertainty from inline amount dict or comp_unc_map
            unc_value = None
            unc_type = ''
            unc_sourcetype = ''
            if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                meta = amount_list[1]
                unc_raw = meta.get('uncertainty')
                if unc_raw is not None:
                    unc_value = float(unc_raw) if isinstance(unc_raw, (int, float)) else None
                    unc_type = meta.get('uncertainty-type', '')
                    unc_sourcetype = meta.get('uncertainty-sourcetype', '')
            if unc_value is None and comp_unc_map and sp_name in comp_unc_map:
                cu = comp_unc_map[sp_name]
                unc_value = cu['value']
                unc_type = cu['kind']
                unc_sourcetype = cu.get('source_type', '')
            
            # ESD from inline or esd_map
            esd_value = None
            esd_type = ''
            esd_sourcetype = ''
            esd_method = ''
            if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                meta = amount_list[1]
                esd_raw = meta.get('evaluated-standard-deviation')
                if esd_raw is not None:
                    esd_value = float(esd_raw) if isinstance(esd_raw, (int, float)) else None
                    esd_type = meta.get('evaluated-standard-deviation-type', '')
                    esd_sourcetype = meta.get('evaluated-standard-deviation-sourcetype', '')
                    esd_method = meta.get('evaluated-standard-deviation-method', '')
            if esd_value is None and esd_map and sp_name in esd_map:
                e = esd_map[sp_name]
                esd_value = e['value']
                esd_type = e['kind']
                esd_sourcetype = e.get('source_type', '')
                esd_method = e.get('method', '')
            
            CompositionSpecies.objects.get_or_create(
                composition=composition,
                species_name=sp_name,
                inchi=sp.get('InChI', ''),
                smiles=sp.get('SMILES', ''),
                defaults={
                    'chem_name': sp.get('chem-name', ''),
                    'cas': sp.get('CAS', ''),
                    'amount': amount_val,
                    'amount_uncertainty': unc_value,
                    'amount_uncertainty_type': unc_type or '',
                    'amount_uncertainty_sourcetype': unc_sourcetype or '',
                    'amount_evaluated_standard_deviation': esd_value,
                    'amount_evaluated_standard_deviation_type': esd_type or '',
                    'amount_evaluated_standard_deviation_sourcetype': esd_sourcetype or '',
                    'amount_evaluated_standard_deviation_method': esd_method or '',
                }
            )
        
        return composition
    
    def _convert_volume_to_si(self, value, units):
        """Convert volume to SI units (m³)."""
        try:
            from pint import UnitRegistry
            ureg = UnitRegistry()
            
            units = units.strip()
            # Handle common volume unit variations
            unit_map = {
                'cm3': 'cm**3',
                'cm^3': 'cm**3',
                'ml': 'mL',
                'l': 'L',
                'm3': 'm**3',
                'm^3': 'm**3',
            }
            units_key = units.lower()
            if units_key in unit_map:
                units = unit_map[units_key]
            
            quantity = ureg.Quantity(value, units)
            return quantity.to('m**3').magnitude
        except Exception as e:
            logger.warning(f"Could not convert volume {value} {units} to SI: {e}")
            return value
    
    def _convert_to_si(self, value, units, quantity_type):
        """Convert a value to SI units using pint."""
        try:
            from pint import UnitRegistry
            ureg = UnitRegistry()
            
            # Handle common unit variations
            units = units.strip()
            unit_map = {
                'torr': 'torr',
                'mmhg': 'mmHg',
                'mm hg': 'mmHg',
                'bar': 'bar',
                'atm': 'atm',
            }
            units_key = units.lower()
            if units_key in unit_map:
                units = unit_map[units_key]
            
            # Create quantity and convert
            quantity = ureg.Quantity(value, units)
            
            if quantity_type == 'temperature':
                return quantity.to('kelvin').magnitude
            elif quantity_type == 'pressure':
                return quantity.to('pascal').magnitude
            elif quantity_type == 'time':
                return quantity.to('second').magnitude
            elif quantity_type == 'velocity':
                return quantity.to('meter / second').magnitude
            else:
                return value
        except Exception as e:
            logger.warning(f"Could not convert {value} {units} to SI: {e}")
            return value

    @transaction.atomic
    def _import_chemked(self, ck, original_filename):
        """Import a ChemKED object into the database."""
        
        # Get or create apparatus
        apparatus, _ = Apparatus.objects.get_or_create(
            kind=ck.apparatus.kind or ApparatusKind.SHOCK_TUBE,
            institution=ck.apparatus.institution or '',
            facility=ck.apparatus.facility or '',
        )
        
        # Create or update dataset (allow re-upload of existing files)
        dataset, created = ExperimentDataset.objects.update_or_create(
            chemked_file_path=original_filename,
            defaults=dict(
                file_version=ck.file_version or 0,
                chemked_version=ck.chemked_version or '0.4.1',
                experiment_type=ck.experiment_type or ExperimentType.IGNITION_DELAY,
                apparatus=apparatus,
                reference_doi=ck.reference.doi or '',
                reference_journal=ck.reference.journal or '',
                reference_year=ck.reference.year,
                reference_volume=ck.reference.volume,
                reference_pages=ck.reference.pages or '',
                reference_detail=ck.reference.detail or '',
            ),
        )
        
        # If updating, clear old related objects so they get re-created
        if not created:
            dataset.datapoints.all().delete()
            dataset.file_authors.clear()
            dataset.reference_authors.clear()
            if hasattr(dataset, 'common_properties') and dataset.common_properties:
                dataset.common_properties.delete()
        
        # Add file authors
        for author in ck.file_authors or []:
            if isinstance(author, dict) and author.get('name'):
                fa, created = FileAuthor.objects.get_or_create(
                    name=author['name'],
                    defaults={'orcid': author.get('ORCID', '')},
                )
                if not created and author.get('ORCID') and not fa.orcid:
                    fa.orcid = author['ORCID']
                    fa.save(update_fields=['orcid'])
                dataset.file_authors.add(fa)
        
        # Add reference authors
        for author in ck.reference.authors or []:
            if isinstance(author, dict) and author.get('name'):
                ra, _ = ReferenceAuthor.objects.get_or_create(
                    name=author['name'],
                    orcid=author.get('ORCID', ''),
                )
                dataset.reference_authors.add(ra)
        
        # Process datapoints
        common_composition = None
        common_composition_type = None
        
        for dp in ck.datapoints:
            # Handle composition
            composition = None
            if dp.composition:
                # Check if same as common composition
                if common_composition is None:
                    common_composition_type = dp.composition_type
                    common_composition = Composition.objects.create(
                        kind=dp.composition_type or CompositionKind.MOLE_FRACTION
                    )
                    for species_name, species in dp.composition.items():
                        CompositionSpecies.objects.create(
                            composition=common_composition,
                            species_name=species_name,
                            inchi=species.InChI or '',
                            smiles=species.SMILES or '',
                            amount=species.amount.magnitude if hasattr(species.amount, 'magnitude') else species.amount,
                        )
                composition = common_composition
            
            # Parse quantities with units
            temp_val = dp.temperature.magnitude if hasattr(dp.temperature, 'magnitude') else dp.temperature
            temp_unit = str(dp.temperature.units) if hasattr(dp.temperature, 'units') else 'K'
            
            press_val = dp.pressure.magnitude if hasattr(dp.pressure, 'magnitude') else dp.pressure
            press_unit = str(dp.pressure.units) if hasattr(dp.pressure, 'units') else 'Pa'
            
            # Convert to SI
            try:
                from pint import UnitRegistry
                ureg = UnitRegistry()
                si_temp = (temp_val * ureg(temp_unit)).to('kelvin').magnitude
                si_press = (press_val * ureg(press_unit)).to('pascal').magnitude
            except:
                si_temp = temp_val
                si_press = press_val
            
            # Create ValueWithUnit objects
            temp_quantity = ValueWithUnit.objects.create(value=temp_val, units=temp_unit)
            press_quantity = ValueWithUnit.objects.create(value=press_val, units=press_unit)
            
            # Create datapoint
            datapoint = ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=si_temp,
                temperature_quantity=temp_quantity,
                pressure=si_press,
                pressure_quantity=press_quantity,
                equivalence_ratio=_unwrap_equiv(dp.equivalence_ratio),
                composition=composition,
            )
            
            # Create ignition delay extension if applicable
            if hasattr(dp, 'ignition_delay') and dp.ignition_delay is not None:
                ign_val = dp.ignition_delay.magnitude if hasattr(dp.ignition_delay, 'magnitude') else dp.ignition_delay
                ign_unit = str(dp.ignition_delay.units) if hasattr(dp.ignition_delay, 'units') else 's'
                
                try:
                    si_ign = (ign_val * ureg(ign_unit)).to('second').magnitude
                except:
                    si_ign = ign_val
                
                ign_quantity = ValueWithUnit.objects.create(value=ign_val, units=ign_unit)
                
                ign_target = ''
                ign_type = ''
                if dp.ignition_type:
                    ign_target = _normalize_ignition_target(dp.ignition_type.get('target', ''))
                    ign_type = dp.ignition_type.get('type', '')
                
                IgnitionDelayDatapoint.objects.create(
                    datapoint=datapoint,
                    ignition_delay=si_ign,
                    ignition_delay_quantity=ign_quantity,
                    ignition_target=ign_target,
                    ignition_type=ign_type,
                )
        
        # Create common properties
        if common_composition:
            # Get ignition info from first datapoint
            first_dp = ck.datapoints[0] if ck.datapoints else None
            ign_target = ''
            ign_type = ''
            if first_dp and first_dp.ignition_type:
                ign_target = _normalize_ignition_target(first_dp.ignition_type.get('target', ''))
                ign_type = first_dp.ignition_type.get('type', '')
            
            CommonProperties.objects.create(
                dataset=dataset,
                composition=common_composition,
                ignition_target=ign_target,
                ignition_type=ign_type,
            )
        
        return dataset


class DatasetExportView(View):
    """
    Export a dataset to ChemKED YAML or ReSpecTh XML format.
    """
    
    def get(self, request, pk):
        dataset = get_object_or_404(
            ExperimentDataset.objects
            .select_related('apparatus', 'common_properties', 'common_properties__composition')
            .prefetch_related(
                'file_authors',
                'reference_authors',
                'datapoints',
                'datapoints__ignition_delay',
                'datapoints__composition__species',
            ),
            pk=pk
        )
        
        export_format = request.GET.get('format', 'yaml')
        
        if export_format == 'yaml':
            return self._export_yaml(dataset)
        elif export_format == 'xml':
            return self._export_xml(dataset)
        elif export_format == 'csv':
            return self._export_csv(dataset)
        else:
            messages.error(request, f'Unknown export format: {export_format}')
            return redirect('chemked_database:dataset-detail', pk=pk)
    
    def _export_yaml(self, dataset):
        """Export dataset to ChemKED YAML format."""
        try:
            from pyked import chemked
            
            # Build ChemKED dictionary from dataset
            chemked_dict = self._dataset_to_chemked_dict(dataset)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                temp_path = f.name
            
            try:
                ck = chemked.ChemKED(dict_input=chemked_dict, skip_validation=True)
                ck.write_file(temp_path, overwrite=True)
                
                with open(temp_path, 'r') as f:
                    yaml_content = f.read()
                
                filename = Path(dataset.chemked_file_path).stem + '.yaml'
                response = HttpResponse(yaml_content, content_type='application/x-yaml')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except ImportError:
            return HttpResponse('PyKED not installed', status=500)
        except Exception as e:
            logger.exception("Error exporting YAML")
            return HttpResponse(f'Error: {str(e)}', status=500)
    
    def _export_xml(self, dataset):
        """Export dataset to ReSpecTh XML format."""
        try:
            from pyked import chemked
            
            chemked_dict = self._dataset_to_chemked_dict(dataset)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml_path = f.name
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                xml_path = f.name
            
            try:
                ck = chemked.ChemKED(dict_input=chemked_dict, skip_validation=True)
                ck.write_file(yaml_path, overwrite=True)
                ck.convert_to_ReSpecTh(xml_path)
                
                with open(xml_path, 'r') as f:
                    xml_content = f.read()
                
                filename = Path(dataset.chemked_file_path).stem + '.xml'
                response = HttpResponse(xml_content, content_type='application/xml')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            finally:
                for p in [yaml_path, xml_path]:
                    if os.path.exists(p):
                        os.unlink(p)
                        
        except Exception as e:
            logger.exception("Error exporting XML")
            return HttpResponse(f'Error: {str(e)}', status=500)
    
    def _export_csv(self, dataset):
        """Export datapoints to CSV format."""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        headers = ['Temperature (K)', 'Pressure (Pa)', 'Equivalence Ratio']
        if dataset.experiment_type == ExperimentType.IGNITION_DELAY:
            headers.append('Ignition Delay (s)')
        
        # Add species columns
        species_names = set()
        for dp in dataset.datapoints.all():
            comp = dp.get_composition()
            if comp:
                for sp in comp.species.all():
                    species_names.add(sp.species_name)
        species_names = sorted(species_names)
        headers.extend([f'{sp} (amount)' for sp in species_names])
        
        writer.writerow(headers)
        
        # Data rows
        for dp in dataset.datapoints.select_related('ignition_delay', 'composition').all():
            row = [dp.temperature, dp.pressure, dp.equivalence_ratio or '']
            
            if dataset.experiment_type == ExperimentType.IGNITION_DELAY:
                if hasattr(dp, 'ignition_delay') and dp.ignition_delay:
                    row.append(dp.ignition_delay.ignition_delay or '')
                else:
                    row.append('')
            
            # Species amounts
            comp = dp.get_composition()
            species_amounts = {}
            if comp:
                for sp in comp.species.all():
                    species_amounts[sp.species_name] = sp.amount
            
            for sp_name in species_names:
                row.append(species_amounts.get(sp_name, ''))
            
            writer.writerow(row)
        
        filename = Path(dataset.chemked_file_path).stem + '.csv'
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    def _dataset_to_chemked_dict(self, dataset):
        """Convert database dataset to ChemKED dictionary."""
        # File authors
        file_authors = []
        for fa in dataset.file_authors.all():
            author = {'name': fa.name}
            if fa.orcid:
                author['ORCID'] = fa.orcid
            file_authors.append(author)
        
        if not file_authors:
            file_authors = [{'name': 'Database Export'}]
        
        # Reference authors
        ref_authors = []
        for ra in dataset.reference_authors.all():
            author = {'name': ra.name}
            if ra.orcid:
                author['ORCID'] = ra.orcid
            ref_authors.append(author)
        
        if not ref_authors:
            ref_authors = [{'name': 'Unknown'}]
        
        # Build composition from common properties or first datapoint
        composition = None
        if hasattr(dataset, 'common_properties') and dataset.common_properties:
            cp = dataset.common_properties
            if cp.composition:
                composition = {
                    'kind': str(cp.composition.kind) if cp.composition.kind else 'mole fraction',
                    'species': []
                }
                for sp in cp.composition.species.all():
                    sp_dict = {
                        'species-name': sp.species_name,
                        'amount': [sp.amount]
                    }
                    if sp.inchi:
                        sp_dict['InChI'] = sp.inchi
                    composition['species'].append(sp_dict)
        
        # Ignition type from common properties
        ignition_type = None
        if hasattr(dataset, 'common_properties') and dataset.common_properties:
            cp = dataset.common_properties
            if cp.ignition_target or cp.ignition_type:
                ignition_type = {}
                if cp.ignition_target:
                    ignition_type['target'] = cp.ignition_target
                if cp.ignition_type:
                    ignition_type['type'] = cp.ignition_type
        
        # Build datapoints
        datapoints = []

        def _serialize_quantity(quantity, fallback_value=None, fallback_units=None):
            if quantity and (quantity.value is not None or quantity.value_text):
                raw_value = quantity.value if quantity.value is not None else quantity.value_text
                unit_part = f" {quantity.units}" if quantity.units else ""
                serialized = [f"{raw_value}{unit_part}".strip()]
            elif fallback_value is not None:
                unit_part = f" {fallback_units}" if fallback_units else ""
                serialized = [f"{fallback_value}{unit_part}".strip()]
            else:
                return None

            metadata = {}

            if quantity:
                if quantity.uncertainty_type:
                    metadata['uncertainty-type'] = quantity.uncertainty_type
                if quantity.uncertainty is not None:
                    metadata['uncertainty'] = quantity.uncertainty
                if quantity.upper_uncertainty is not None:
                    metadata['upper-uncertainty'] = quantity.upper_uncertainty
                if quantity.lower_uncertainty is not None:
                    metadata['lower-uncertainty'] = quantity.lower_uncertainty
                if quantity.evaluated_standard_deviation is not None:
                    metadata['evaluated-standard-deviation'] = quantity.evaluated_standard_deviation
                if quantity.evaluated_standard_deviation_type:
                    metadata['evaluated-standard-deviation-type'] = quantity.evaluated_standard_deviation_type
                if quantity.evaluated_standard_deviation_sourcetype:
                    metadata['evaluated-standard-deviation-sourcetype'] = quantity.evaluated_standard_deviation_sourcetype
                if quantity.evaluated_standard_deviation_method:
                    metadata['evaluated-standard-deviation-method'] = quantity.evaluated_standard_deviation_method

            if metadata:
                serialized.append(metadata)

            return serialized

        for dp in dataset.datapoints.all():
            dp_dict = {}
            
            # Temperature
            temp_entry = _serialize_quantity(
                dp.temperature_quantity,
                fallback_value=dp.temperature,
                fallback_units='kelvin',
            )
            if temp_entry:
                dp_dict['temperature'] = temp_entry
            
            # Pressure (omit placeholder 0.0)
            pressure_fallback = dp.pressure if dp.pressure and dp.pressure != 0.0 else None
            pressure_entry = _serialize_quantity(
                dp.pressure_quantity,
                fallback_value=pressure_fallback,
                fallback_units='pascal',
            )
            if pressure_entry:
                dp_dict['pressure'] = pressure_entry
            
            # Equivalence ratio
            if dp.equivalence_ratio:
                dp_dict['equivalence-ratio'] = dp.equivalence_ratio
            
            # Composition
            if composition:
                dp_dict['composition'] = composition
            elif dp.composition:
                dp_dict['composition'] = {
                    'kind': str(dp.composition.kind) if dp.composition.kind else 'mole fraction',
                    'species': [
                        {'species-name': sp.species_name, 'amount': [sp.amount]}
                        for sp in dp.composition.species.all()
                    ]
                }
            
            # Ignition type
            if ignition_type:
                dp_dict['ignition-type'] = ignition_type
            
            # Ignition delay
            if hasattr(dp, 'ignition_delay') and dp.ignition_delay:
                ign = dp.ignition_delay
                ign_entry = _serialize_quantity(
                    ign.ignition_delay_quantity,
                    fallback_value=ign.ignition_delay,
                    fallback_units='s',
                )
                if ign_entry:
                    dp_dict['ignition-delay'] = ign_entry

            # Laminar burning velocity
            if hasattr(dp, 'laminar_burning_velocity_measurement'):
                try:
                    lbv = dp.laminar_burning_velocity_measurement
                    if lbv and lbv.laminar_burning_velocity is not None:
                        lbv_entry = _serialize_quantity(
                            lbv.laminar_burning_velocity_quantity,
                            fallback_value=lbv.laminar_burning_velocity,
                            fallback_units='m/s',
                        )
                        if lbv_entry:
                            dp_dict['laminar-burning-velocity'] = lbv_entry
                except dp.__class__.laminar_burning_velocity_measurement.RelatedObjectDoesNotExist:
                    pass

            # Measured quantity (for kdetermination files)
            if hasattr(dp, 'rate_coefficient'):
                try:
                    rc = dp.rate_coefficient
                    if rc and rc.rate_coefficient is not None:
                        yaml_key = (
                            'branching-ratio'
                            if rc.measurement_type == MeasurementType.BRANCHING_RATIO
                            else 'rate-coefficient'
                        )
                        rc_entry = _serialize_quantity(
                            rc.rate_coefficient_quantity,
                            fallback_value=rc.rate_coefficient,
                            fallback_units=rc.rate_coefficient_units,
                        )
                        if rc_entry:
                            dp_dict[yaml_key] = rc_entry
                except dp.__class__.rate_coefficient.RelatedObjectDoesNotExist:
                    pass

            datapoints.append(dp_dict)
        
        # Ensure experiment-type is a plain string (not Django TextChoices enum)
        exp_type = dataset.experiment_type or 'ignition delay'
        exp_type_str = f"{exp_type}"  # Force plain str from TextChoices

        chemked_dict = {
            'file-version': dataset.file_version or 0,
            'chemked-version': dataset.chemked_version or '0.4.1',
            'file-authors': file_authors,
            'reference': {
                'doi': dataset.reference_doi or '',
                'authors': ref_authors,
                'journal': dataset.reference_journal or '',
                'year': dataset.reference_year or 2020,
                'pages': dataset.reference_pages or '',
                'detail': dataset.reference_detail or '',
            },
            'experiment-type': exp_type_str,
            'apparatus': {k: v for k, v in {
                'kind': f"{dataset.apparatus.kind}" if dataset.apparatus else 'shock tube',
                'institution': dataset.apparatus.institution if dataset.apparatus else '',
                'facility': dataset.apparatus.facility if dataset.apparatus else '',
            }.items() if v},
            'datapoints': datapoints,
        }
        
        if dataset.reference_volume:
            chemked_dict['reference']['volume'] = dataset.reference_volume

        # For rate coefficient experiments, add reaction and method info
        if exp_type_str == 'rate coefficient':
            first_dp = dataset.datapoints.first()
            if first_dp:
                try:
                    rc = first_dp.rate_coefficient
                    if rc:
                        if rc.reaction:
                            chemked_dict['reaction'] = rc.reaction
                        if rc.method:
                            chemked_dict['method'] = rc.method
                        if rc.bulk_gas:
                            chemked_dict['bulk-gas'] = rc.bulk_gas
                except first_dp.__class__.rate_coefficient.RelatedObjectDoesNotExist:
                    pass

            # Fallback: extract reaction from reference_detail if not found
            if 'reaction' not in chemked_dict and dataset.reference_detail:
                import re as _re
                m = _re.search(r'Reaction:\s*(.+)', dataset.reference_detail)
                if m:
                    chemked_dict['reaction'] = m.group(1).strip()

        return chemked_dict


class DatasetProcessView(View):
    """
    SSE endpoint for processing uploaded files with real-time progress.
    
    This view receives a batch_id from session, processes files one by one,
    and streams progress updates back to the client.
    """
    
    def get(self, request):
        """Stream processing progress via Server-Sent Events."""
        batch_id = request.GET.get('batch_id')
        
        if not batch_id:
            return JsonResponse({'error': 'No batch_id provided'}, status=400)
        
        # Get batch data from session
        batch_key = f'upload_batch_{batch_id}'
        batch_data = request.session.get(batch_key)
        
        if not batch_data:
            return JsonResponse({'error': 'Batch not found or expired'}, status=404)
        
        # Clear session data immediately
        del request.session[batch_key]
        request.session.modified = True
        
        # Create SSE response
        response = StreamingHttpResponse(
            self._process_files_stream(batch_data, request),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        return response
    
    def _process_files_stream(self, batch_data, request):
        """Generator that processes files and yields SSE events."""
        temp_files = batch_data.get('temp_files', [])
        file_format = batch_data.get('file_format', 'auto')
        validate = batch_data.get('validate', True)
        file_author = batch_data.get('file_author', '')
        file_author_orcid = batch_data.get('file_author_orcid', '')
        contribute_to_github = batch_data.get('contribute_to_github', False)
        run_pyteck = batch_data.get('run_pyteck', False)
        github_username = batch_data.get('github_username', '')
        contribution_description = batch_data.get('contribution_description', '')
        
        total_files = len(temp_files)
        successful_imports = []
        skipped_imports = []
        failed_imports = []
        
        # Send initial event
        yield self._sse_event('start', {
            'total': total_files,
            'message': f'Starting to process {total_files} file(s)...'
        })
        
        # Get the upload view for processing methods
        upload_view = DatasetUploadView()
        upload_view.request = request
        
        for i, file_info in enumerate(temp_files):
            temp_path = file_info['temp_path']
            original_name = file_info['original_name']
            
            # Send progress event
            progress = ((i + 0.5) / total_files) * 100
            yield self._sse_event('progress', {
                'current': i + 1,
                'total': total_files,
                'percent': round(progress, 1),
                'filename': original_name,
                'message': f'Processing {original_name}...'
            })
            
            # Process the file
            try:
                if not os.path.exists(temp_path):
                    raise FileNotFoundError(f'Temporary file not found: {temp_path}')
                
                # Read file content before processing if we need it for PR creation
                file_content_for_pr = None
                pr_filename = original_name
                if contribute_to_github:
                    if original_name.lower().endswith('.xml'):
                        # For XML files, convert to YAML so the PR
                        # contributes ChemKED YAML to the database repo.
                        try:
                            from pyked.batch_convert import convert_file as _conv
                            chemked_dict = _conv(temp_path, original_filename=original_name)
                            file_content_for_pr = format_chemked_yaml(chemked_dict).encode('utf-8')
                        except Exception:
                            logger.debug("XML→YAML conversion for PR failed; will use raw content")
                            with open(temp_path, 'rb') as fh:
                                file_content_for_pr = fh.read()
                    else:
                        with open(temp_path, 'rb') as fh:
                            file_content_for_pr = fh.read()

                result = self._process_single_file(
                    upload_view, temp_path, original_name, 
                    file_format, validate, file_author, file_author_orcid
                )
                
                if result['success']:
                    successful_imports.append(result)
                    if file_content_for_pr is not None:
                        result['_content'] = file_content_for_pr
                        # Use the readable dataset name for the PR filename
                        ds_name = result.get('dataset_name', '')
                        if ds_name and original_name.lower().endswith('.xml'):
                            pr_filename = Path(ds_name).stem + '.yaml'
                        result['filename'] = pr_filename
                    yield self._sse_event('file_complete', {
                        'filename': original_name,
                        'status': 'success',
                        'dataset_name': result.get('dataset_name', ''),
                        'datapoints': result.get('datapoints', 0)
                    })
                else:
                    if result.get('error_kind') == 'skipped':
                        skipped_imports.append(result)
                        yield self._sse_event('file_complete', {
                            'filename': original_name,
                            'status': 'skipped',
                            'error': result.get('error', 'Skipped')
                        })
                    else:
                        failed_imports.append(result)
                        yield self._sse_event('file_complete', {
                            'filename': original_name,
                            'status': 'failed',
                            'error': result.get('error', 'Unknown error')
                        })
            except Exception as e:
                logger.exception(f"Error processing {original_name}")
                failed_imports.append({
                    'success': False,
                    'filename': original_name,
                    'error': str(e)
                })
                yield self._sse_event('file_complete', {
                    'filename': original_name,
                    'status': 'failed',
                    'error': str(e)
                })
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
            
            # Update progress after file is complete
            progress = ((i + 1) / total_files) * 100
            yield self._sse_event('progress', {
                'current': i + 1,
                'total': total_files,
                'percent': round(progress, 1),
                'filename': original_name,
                'message': f'Completed {i + 1} of {total_files}'
            })
        
        # Create GitHub PR if requested and there are successful imports
        pr_result = None
        if contribute_to_github and successful_imports:
            yield self._sse_event('progress', {
                'current': total_files,
                'total': total_files,
                'percent': 95,
                'filename': '',
                'message': 'Creating GitHub pull request...'
            })
            try:
                pr_result = self._create_contribution_pr_from_batch(
                    temp_files, successful_imports,
                    file_author, file_author_orcid,
                    run_pyteck, contribution_description,
                    github_username=github_username,
                )
                if pr_result:
                    yield self._sse_event('pr_created', {
                        'pr_url': pr_result['pr_url'],
                        'pr_number': pr_result['pr_number'],
                        'branch': pr_result['branch'],
                    })
            except Exception as exc:
                logger.exception("Failed to create contribution PR during SSE processing")
                yield self._sse_event('pr_error', {
                    'error': str(exc),
                })

        # Create Submission record
        submission = None
        if successful_imports:
            submission = Submission.objects.create(
                status=Submission.Status.SUCCESS if not failed_imports else Submission.Status.PARTIAL,
                successful_imports=[
                    {k: v for k, v in r.items() if k != '_content'}
                    for r in successful_imports
                ],
                failed_imports=failed_imports,
                skipped_imports=skipped_imports,
                contributor_name=file_author,
                contributor_orcid=file_author_orcid,
                pr_url=pr_result.get('pr_url', '') if pr_result else '',
                pr_number=pr_result.get('pr_number') if pr_result else None,
                branch=pr_result.get('branch', '') if pr_result else '',
            )

        # Send completion event
        total_datapoints = sum(r.get('datapoints', 0) for r in successful_imports)
        redirect_url = None
        if submission:
            redirect_url = reverse('chemked_database:submission-status', kwargs={'pk': submission.pk})
        completion_data = {
            'successful': len(successful_imports),
            'skipped': len(skipped_imports),
            'failed': len(failed_imports),
            'total_datapoints': total_datapoints,
            'redirect_url': redirect_url,
        }
        if pr_result:
            completion_data['pr_url'] = pr_result['pr_url']
            completion_data['pr_number'] = pr_result['pr_number']
        yield self._sse_event('complete', completion_data)
    
    def _process_single_file(self, upload_view, temp_path, original_name, file_format, validate, file_author, file_author_orcid):
        """Process a single file and return result dict."""
        filename = original_name.lower()
        
        # Determine file format
        actual_format = file_format
        if actual_format == 'auto':
            if filename.endswith('.xml'):
                actual_format = 'xml'
            else:
                actual_format = 'yaml'
        
        try:
            if actual_format == 'xml':
                dataset = upload_view._import_respecth_xml_batch(temp_path, original_name, file_author, file_author_orcid)
                return {
                    'success': True,
                    'filename': original_name,
                    'dataset_id': dataset.pk,
                    'dataset_name': dataset.chemked_file_path,
                    'datapoints': dataset.datapoints.count()
                }
            else:
                from pyked import chemked
                ck = chemked.ChemKED(yaml_file=temp_path, skip_validation=not validate)
                dataset = upload_view._import_chemked(ck, original_name)
                return {
                    'success': True,
                    'filename': original_name,
                    'dataset_id': dataset.pk,
                    'dataset_name': dataset.chemked_file_path,
                    'datapoints': dataset.datapoints.count()
                }
        except Exception as e:
            formatted = upload_view._format_import_error(str(e))
            return {
                'success': False,
                'filename': original_name,
                'error': formatted['message'],
                'error_kind': formatted['kind']
            }
    
    def _create_contribution_pr_from_batch(self, temp_files, successful_imports,
                                            file_author, file_author_orcid,
                                            run_pyteck=False, contribution_description='',
                                            github_username=''):
        """Create a GitHub PR using file content cached from SSE batch processing."""
        from .github_pr_service import GitHubPRService, GitHubContributionError

        try:
            gh = GitHubPRService(
                token=getattr(settings, 'GITHUB_TOKEN', ''),
                owner=getattr(settings, 'GITHUB_REPO_OWNER', ''),
                repo=getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database'),
            )
        except GitHubContributionError as exc:
            logger.warning("GitHub PR service not configured: %s", exc)
            return None

        pr_files = []
        for result in successful_imports:
            content = result.get('_content')
            if content is None:
                continue
            repo_path = gh.determine_repo_path(result['filename'], content)
            pr_files.append({'path': repo_path, 'content': content})

        if not pr_files:
            logger.warning("No file content available for PR creation; skipping.")
            return None

        file_type = 'chemked'
        if any(f['path'].lower().endswith('.xml') for f in pr_files):
            file_type = 'respecth'

        try:
            return gh.contribute_files(
                files=pr_files,
                contributor_name=file_author or 'Anonymous',
                contributor_orcid=file_author_orcid,
                file_type=file_type,
                description=contribution_description,
                run_pyteck=run_pyteck,
                github_username=github_username,
                validation_passed=True,
            )
        except GitHubContributionError as exc:
            logger.exception("Failed to create contribution PR from batch")
            return None

    def _sse_event(self, event_type, data):
        """Format a Server-Sent Event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


class ClearWizardView(View):
    """Clear the wizard session data."""
    
    def get(self, request):
        """Allow GET for simple link-based clearing."""
        return self._clear_session(request)
    
    def post(self, request):
        return self._clear_session(request)
    
    def _clear_session(self, request):
        if 'chemked_wizard' in request.session:
            del request.session['chemked_wizard']
        messages.info(request, 'Form data cleared.')
        return redirect('chemked_database:dataset-create')


# ------------------------------------------------------------------
# Submission Status
# ------------------------------------------------------------------

class SubmissionStatusView(DetailView):
    """Show the status of a dataset upload submission."""
    model = Submission
    template_name = 'chemked_database/submission_status.html'
    context_object_name = 'submission'


class SubmissionCheckRunsView(View):
    """AJAX endpoint: poll GitHub Actions check runs for a submission's PR.

    Returns check-run status **and** annotations (validation messages)
    so the submission-status page can show the actual CI output inline.
    """

    def get(self, request, pk):
        submission = get_object_or_404(Submission, pk=pk)
        if not submission.pr_number or not submission.branch:
            return JsonResponse({'check_runs': [], 'status': 'no_pr'})

        import requests as http_requests
        from .github_pr_service import GitHubContributionError

        token = getattr(settings, 'GITHUB_TOKEN', '') or os.environ.get('GITHUB_TOKEN', '')
        owner = getattr(settings, 'GITHUB_REPO_OWNER', '') or os.environ.get('GITHUB_REPO_OWNER', '')
        repo = getattr(settings, 'GITHUB_REPO_NAME', 'ChemKED-database') or os.environ.get('GITHUB_REPO_NAME', 'ChemKED-database')

        if not token or not owner:
            return JsonResponse({'check_runs': [], 'status': 'not_configured'})

        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github+json',
        }
        try:
            # Get HEAD SHA of the branch
            ref_resp = http_requests.get(
                f'https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{submission.branch}',
                headers=headers, timeout=10,
            )
            if ref_resp.status_code != 200:
                return JsonResponse({'check_runs': [], 'status': 'branch_not_found'})
            head_sha = ref_resp.json()['object']['sha']

            # Get check runs for that SHA
            checks_resp = http_requests.get(
                f'https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs',
                headers=headers, timeout=10,
            )
            if checks_resp.status_code != 200:
                return JsonResponse({'check_runs': [], 'status': 'api_error'})

            data = checks_resp.json()
            runs = []
            for cr in data.get('check_runs', []):
                run = {
                    'id': cr['id'],
                    'name': cr['name'],
                    'status': cr['status'],           # queued, in_progress, completed
                    'conclusion': cr.get('conclusion'),  # success, failure, ...
                    'html_url': cr.get('html_url', ''),
                    'started_at': cr.get('started_at', ''),
                    'completed_at': cr.get('completed_at', ''),
                    'annotations': [],
                    'output_title': '',
                    'output_summary': '',
                }

                # Include output title/summary if available
                output = cr.get('output') or {}
                run['output_title'] = output.get('title') or ''
                run['output_summary'] = output.get('summary') or ''

                # Fetch annotations (actual validation error messages)
                ann_count = output.get('annotations_count', 0)
                if ann_count and cr['status'] == 'completed':
                    try:
                        ann_resp = http_requests.get(
                            f'https://api.github.com/repos/{owner}/{repo}/check-runs/{cr["id"]}/annotations',
                            headers=headers, timeout=10,
                        )
                        if ann_resp.status_code == 200:
                            for a in ann_resp.json():
                                run['annotations'].append({
                                    'level': a.get('annotation_level', ''),   # notice, warning, failure
                                    'message': a.get('message', ''),
                                    'title': a.get('title', ''),
                                    'path': a.get('path', ''),
                                })
                    except http_requests.RequestException:
                        pass  # annotations are best-effort

                runs.append(run)

            # Also fetch workflow run for a link to the full log page
            workflow_url = ''
            try:
                wf_resp = http_requests.get(
                    f'https://api.github.com/repos/{owner}/{repo}/actions/runs?head_sha={head_sha}',
                    headers=headers, timeout=10,
                )
                if wf_resp.status_code == 200:
                    wf_runs = wf_resp.json().get('workflow_runs', [])
                    if wf_runs:
                        workflow_url = wf_runs[0].get('html_url', '')
            except http_requests.RequestException:
                pass

            # Overall status
            if not runs:
                overall = 'pending'
            elif all(r['status'] == 'completed' for r in runs):
                if all(r['conclusion'] == 'success' for r in runs):
                    overall = 'success'
                else:
                    overall = 'failure'
            else:
                overall = 'in_progress'

            return JsonResponse({
                'check_runs': runs,
                'status': overall,
                'workflow_url': workflow_url,
            })
        except http_requests.RequestException as exc:
            logger.warning('GitHub API error checking runs: %s', exc)
            return JsonResponse({'check_runs': [], 'status': 'api_error'})
