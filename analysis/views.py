"""
Analysis Views
"""

import json
import tempfile
import logging
import os
from django.conf import settings
from typing import Optional

from django.contrib import messages
from kms.access import SiteLoginRequiredMixin
from django.db.models import Count, Avg, Min, Max, Q, F
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView, DetailView, ListView, FormView

from database.models import KineticModel
from chemked_database.models import ExperimentDataset, CompositionSpecies

from .models import (
    SimulationRun,
    SimulationResult,
    DatapointResult,
    SpeciesMapping,
    ModelDatasetCoverage,
    SimulationStatus,
    TriggerType,
)
from .forms import SimulationCreateForm, DatasetFilterForm, SpeciesMappingReviewFormSet
from .services import (
    run_pyteck_simulation,
    parse_pyteck_results,
    build_spec_keys_for_dataset,
    get_cantera_mechanism_from_model,
)

logger = logging.getLogger(__name__)


def _get_simulation_log_dir():
    """Return the persistent log directory for simulation runs."""
    base_dir = getattr(settings, "BASE_DIR", os.getcwd())
    log_dir = os.path.join(base_dir, "analysis", "run_logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _get_simulation_results_dir(run_id: int):
    """Return a per-run results directory inside the app folder."""
    base_dir = getattr(settings, "BASE_DIR", os.getcwd())
    results_dir = os.path.join(base_dir, "analysis", "run_results", f"run_{run_id}")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir


def _append_simulation_log(run: SimulationRun, message: str):
    """Append a message to the shared simulation log file."""
    log_dir = _get_simulation_log_dir()
    log_path = os.path.join(log_dir, "simulation_runs.log")
    timestamp = timezone.now().isoformat()
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] Run #{run.pk} - {message}\n")


class AnalysisDashboardView(TemplateView):
    """
    Main analysis dashboard with overview statistics and recent runs.
    """
    template_name = "analysis/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Overall statistics
        context["total_models"] = KineticModel.objects.count()
        context["total_datasets"] = ExperimentDataset.objects.filter(
            experiment_type='ignition delay'
        ).count()
        context["total_runs"] = SimulationRun.objects.count()
        context["successful_runs"] = SimulationRun.objects.filter(
            status=SimulationStatus.COMPLETED
        ).count()

        # Coverage statistics
        coverage_stats = ModelDatasetCoverage.objects.aggregate(
            total_pairs=Count('id'),
            evaluated_pairs=Count('id', filter=Q(has_successful_run=True)),
            outdated_pairs=Count('id', filter=Q(is_outdated=True)),
        )
        context["coverage_stats"] = coverage_stats
        
        # Calculate coverage percentage
        total_possible = context["total_models"] * context["total_datasets"]
        if total_possible > 0:
            context["coverage_percent"] = round(
                coverage_stats['evaluated_pairs'] / total_possible * 100, 1
            )
        else:
            context["coverage_percent"] = 0

        # Recent simulation runs
        context["recent_runs"] = (
            SimulationRun.objects
            .select_related('kinetic_model', 'dataset', 'result')
            .order_by('-created_at')[:10]
        )

        # Models with most coverage
        context["top_models"] = (
            KineticModel.objects
            .annotate(
                coverage_count=Count('dataset_coverage', filter=Q(dataset_coverage__has_successful_run=True))
            )
            .order_by('-coverage_count')[:5]
        )

        # Best performing model-dataset pairs
        context["best_performers"] = (
            ModelDatasetCoverage.objects
            .filter(has_successful_run=True, latest_error_function__isnull=False)
            .select_related('kinetic_model', 'dataset')
            .order_by('latest_error_function')[:10]
        )

        # Runs needing attention (outdated or failed)
        context["needs_attention"] = (
            ModelDatasetCoverage.objects
            .filter(Q(is_outdated=True) | Q(needs_rerun=True))
            .select_related('kinetic_model', 'dataset')[:10]
        )

        return context


class SimulationCreateView(FormView):
    """
    Create new simulation runs.
    """
    template_name = "analysis/simulation_form.html"
    form_class = SimulationCreateForm
    success_url = reverse_lazy('analysis:dashboard')

    def _dataset_ids_for_fuel_keyword(self, keyword: str):
        if not keyword:
            return []
        keyword = keyword.strip()
        if not keyword:
            return []

        query = (
            Q(species_name__icontains=keyword)
            | Q(chem_name__icontains=keyword)
            | Q(cas__icontains=keyword)
            | Q(inchi__icontains=keyword)
            | Q(smiles__icontains=keyword)
        )

        return (
            CompositionSpecies.objects
            .filter(query)
            .values_list('composition__datapoints__dataset_id', flat=True)
            .distinct()
        )

    def _get_filter_form(self):
        return DatasetFilterForm(self.request.GET or None)

    def _get_filtered_datasets(self):
        qs = ExperimentDataset.objects.all()
        filter_form = self._get_filter_form()

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get('experiment_type'):
                qs = qs.filter(experiment_type=data['experiment_type'])
            if data.get('apparatus_kind'):
                qs = qs.filter(apparatus__kind=data['apparatus_kind'])
            if data.get('min_temperature') is not None:
                qs = qs.filter(datapoints__temperature__gte=data['min_temperature'])
            if data.get('max_temperature') is not None:
                qs = qs.filter(datapoints__temperature__lte=data['max_temperature'])

            fuel_keyword = data.get('fuel_species')
            if fuel_keyword:
                dataset_ids = self._dataset_ids_for_fuel_keyword(fuel_keyword)
                qs = qs.filter(id__in=dataset_ids)

        return qs.distinct()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['dataset_queryset'] = self._get_filtered_datasets()

        # Pre-select model from ?model=<pk> query param (e.g. from fuel-map)
        model_pk = self.request.GET.get('model')
        if model_pk:
            try:
                kwargs['initial_model'] = KineticModel.objects.get(pk=model_pk)
            except (KineticModel.DoesNotExist, ValueError):
                pass

        # Pre-select datasets from ?fuel=<pk> (fuel-map play button)
        fuel_pk = self.request.GET.get('fuel')
        if fuel_pk:
            try:
                from .models import FuelSpecies
                fuel = FuelSpecies.objects.get(pk=fuel_pk)
                kwargs['initial_fuel'] = fuel
            except (FuelSpecies.DoesNotExist, ValueError):
                pass

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["models"] = KineticModel.objects.all()
        context["datasets"] = (
            ExperimentDataset.objects
            .select_related('common_properties')
            .prefetch_related('datapoints')
            .order_by('chemked_file_path')
        )

        # Pass pre-selected dataset IDs to JS (from fuel-map play button)
        form = context.get('form')
        initial_ds = form.fields['datasets'].initial if form else None
        if initial_ds:
            context['preselected_dataset_ids'] = json.dumps(list(initial_ds))
        else:
            context['preselected_dataset_ids'] = '[]'

        # Pass fuel info for banner
        if form and hasattr(form, 'fuel_info'):
            context['fuel_info'] = form.fuel_info

        # Pass pre-selected model ID for JS
        model_pk = self.request.GET.get('model', '')
        context['preselected_model_id'] = model_pk

        return context

    def form_valid(self, form):
        model = form.cleaned_data['kinetic_model']
        datasets = form.cleaned_data['datasets']
        skip_validation = form.cleaned_data['skip_validation']
        auto_execute = form.cleaned_data.get('auto_execute', True)  # Default to auto-execute

        created_runs = []
        for dataset in datasets:
            run = SimulationRun.objects.create(
                kinetic_model=model,
                dataset=dataset,
                status=SimulationStatus.PENDING,
                triggered_by=TriggerType.MANUAL,
                triggered_by_user=self.request.user if self.request.user.is_authenticated else None,
                skip_validation=skip_validation,
                model_version_hash=SimulationRun.compute_model_hash(model),
            )
            # Persist per-run results directory inside app folder
            run.results_dir = _get_simulation_results_dir(run.pk)
            run.save(update_fields=['results_dir'])
            created_runs.append(run)

        # If auto_execute is OFF → redirect to species mapping review
        if not auto_execute:
            run_ids = ','.join(str(r.pk) for r in created_runs)
            messages.info(
                self.request,
                f"Created {len(created_runs)} simulation run(s). "
                f"Review species mappings before executing."
            )
            if len(created_runs) == 1:
                return redirect('analysis:mapping-review', pk=created_runs[0].pk)
            # Multiple runs: redirect to first, rest queued
            return redirect(
                reverse('analysis:mapping-review', kwargs={'pk': created_runs[0].pk})
                + f'?next_runs={",".join(str(r.pk) for r in created_runs[1:])}'
            )

        # Auto-execute: start simulations immediately
        for run in created_runs:
            execute_simulation_async(run.pk)

        messages.success(
            self.request,
            f"Created {len(created_runs)} simulation run(s). Execution started automatically."
        )

        # If only one run, redirect to its detail page
        if len(created_runs) == 1:
            return redirect('analysis:run-detail', pk=created_runs[0].pk)
        
        # Multiple runs - redirect to runs list
        return redirect('analysis:run-list')


def execute_simulation_async(run_id):
    """
    Execute a simulation in a background thread.
    This allows the request to return immediately while simulation runs.
    """
    import threading
    
    def _run():
        import django
        django.setup()
        
        from analysis.models import SimulationRun, SimulationResult, DatapointResult, SimulationStatus, ModelDatasetCoverage
        from analysis.services import run_pyteck_simulation, parse_pyteck_results
        import tempfile
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            run = SimulationRun.objects.get(pk=run_id)
            
            if run.status not in [SimulationStatus.PENDING, SimulationStatus.FAILED]:
                return
            
            _append_simulation_log(run, "Starting simulation")
            run.mark_running()
            
            # Ensure results directory exists and is persisted
            results_dir = run.results_dir
            if not results_dir or not os.path.isdir(results_dir):
                results_dir = _get_simulation_results_dir(run.pk)
                run.results_dir = results_dir
                run.save(update_fields=['results_dir'])
            
            success, message, results = run_pyteck_simulation(
                model=run.kinetic_model,
                dataset=run.dataset,
                results_dir=results_dir,
                skip_validation=run.skip_validation,
            )
            
            if success and results:
                run.mark_completed()
                _append_simulation_log(run, "Simulation completed successfully")
                
                parsed = parse_pyteck_results(results)
                
                total_dp = sum(len(ds['datapoints']) for ds in parsed['datasets'])
                failed_dp = sum(
                    1 for ds in parsed['datasets']
                    for dp in ds['datapoints']
                    if not dp.get('ignition_detected', True)
                )
                
                result = SimulationResult.objects.create(
                    simulation_run=run,
                    average_error_function=parsed['average_error_function'],
                    average_deviation_function=parsed['average_deviation_function'],
                    results_json=results,
                    num_datapoints=total_dp,
                    num_successful=total_dp - failed_dp,
                    num_failed=failed_dp,
                )
                
                for ds in parsed['datasets']:
                    for dp in ds['datapoints']:
                        temp = _parse_value_with_unit(dp.get('temperature'))
                        pressure = _parse_value_with_unit(dp.get('pressure'))
                        exp_delay = _parse_value_with_unit(dp.get('experimental_ignition_delay'))
                        sim_delay = _parse_value_with_unit(dp.get('simulated_ignition_delay'))
                        
                        ignition_ok = dp.get('ignition_detected', True)
                        
                        if temp and pressure and exp_delay:
                            DatapointResult.objects.create(
                                simulation_result=result,
                                temperature=temp,
                                pressure=pressure,
                                composition=dp.get('composition', []),
                                experimental_ignition_delay=exp_delay,
                                simulated_ignition_delay=sim_delay,
                                success=ignition_ok,
                                error_message=dp.get('note', '') if not ignition_ok else '',
                            )
                
                if failed_dp:
                    _append_simulation_log(
                        run,
                        f"WARNING: Ignition was not detected for {failed_dp} of "
                        f"{total_dp} datapoint(s). A sentinel value of 1e10 s was "
                        f"used for the simulated ignition delay of those points."
                    )
                
                # Update coverage matrix
                coverage, _ = ModelDatasetCoverage.objects.get_or_create(
                    kinetic_model=run.kinetic_model,
                    dataset=run.dataset,
                )
                coverage.update_from_run(run)
            else:
                run.mark_failed(message)
                _append_simulation_log(run, f"Simulation failed: {message}")
                
        except Exception as e:
            import traceback
            logger.exception(f"Background simulation {run_id} failed")
            try:
                run = SimulationRun.objects.get(pk=run_id)
                run.mark_failed(str(e), traceback.format_exc())
                _append_simulation_log(run, f"Simulation crashed: {e}")
            except:
                pass
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Species Mapping Review (pre-simulation)
# ---------------------------------------------------------------------------

class SpeciesMappingReviewView(TemplateView):
    """
    Pre-simulation review page that shows the auto-generated species
    mapping for a pending SimulationRun, letting the user correct any
    mismatches before executing.

    Flow:
        SimulationCreateView (auto_execute=off)
          → redirect here
          → user reviews / edits mapping table
          → POST saves overrides + launches simulation
    """
    template_name = "analysis/mapping_review.html"

    def _get_run(self):
        return get_object_or_404(
            SimulationRun.objects.select_related('kinetic_model', 'dataset'),
            pk=self.kwargs['pk'],
        )

    def _build_initial_data(self, run):
        """Compute the auto-matched mapping and return formset initial data."""
        spec_keys = build_spec_keys_for_dataset(
            run.kinetic_model, run.dataset
        )

        # Determine confidence / method per entry by checking SpeciesMapping
        saved = {
            sm.dataset_species_name: sm
            for sm in SpeciesMapping.objects.filter(
                kinetic_model=run.kinetic_model,
                dataset_species_name__in=spec_keys.keys(),
            ).filter(
                Q(dataset=run.dataset) | Q(dataset__isnull=True)
            )
        }

        # Load mechanism species for the dropdown hint
        try:
            mechanism_path = get_cantera_mechanism_from_model(run.kinetic_model)
            from .services.simulation import get_mechanism_species_names
            mech_species = set(get_mechanism_species_names(mechanism_path)) if mechanism_path else set()
        except Exception:
            mech_species = set()

        initial = []
        for ds_label, mapped_name in spec_keys.items():
            sm = saved.get(ds_label)
            in_mechanism = mapped_name in mech_species
            initial.append({
                'dataset_species_name': ds_label,
                'original_model_species_name': mapped_name,
                'model_species_name': mapped_name,
                'confidence': sm.confidence if sm else (0.9 if in_mechanism else 0.3),
                'mapping_method': sm.mapping_method if sm else ('auto' if in_mechanism else 'fallback'),
                'is_override': False,
                'override_reason': '',
            })

        return initial, mech_species

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run = self._get_run()
        initial, mech_species = self._build_initial_data(run)

        context['run'] = run
        context['formset'] = SpeciesMappingReviewFormSet(initial=initial)
        context['mech_species_json'] = json.dumps(sorted(mech_species))
        context['next_runs'] = self.request.GET.get('next_runs', '')
        return context

    def post(self, request, pk):
        run = self._get_run()
        formset = SpeciesMappingReviewFormSet(request.POST)

        if not formset.is_valid():
            initial, mech_species = self._build_initial_data(run)
            return self.render_to_response({
                'run': run,
                'formset': formset,
                'mech_species_json': json.dumps(sorted(mech_species)),
                'next_runs': request.POST.get('next_runs', ''),
            })

        # Save overrides to SpeciesMapping + build spec_keys_snapshot
        spec_keys_snapshot = {}
        user = request.user if request.user.is_authenticated else None

        for form_data in formset.cleaned_data:
            ds_name = form_data['dataset_species_name']
            model_name = form_data['model_species_name']
            original = form_data.get('original_model_species_name', '')
            spec_keys_snapshot[ds_name] = model_name

            # Detect if the user changed the mapping
            was_edited = (model_name != original)

            # Upsert the SpeciesMapping row
            sm, created = SpeciesMapping.objects.update_or_create(
                kinetic_model=run.kinetic_model,
                dataset=run.dataset,
                dataset_species_name=ds_name,
                defaults={
                    'model_species_name': model_name,
                    'mapping_method': 'manual' if was_edited else (
                        form_data.get('mapping_method') or 'fallback'
                    ),
                    'confidence': 1.0 if was_edited else (
                        form_data.get('confidence') or 0.5
                    ),
                    'is_manual_override': was_edited,
                    'override_by': user if was_edited else None,
                    'override_reason': form_data.get('override_reason', '') if was_edited else '',
                },
            )

        # Persist snapshot on the run
        run.spec_keys_snapshot = spec_keys_snapshot
        run.save(update_fields=['spec_keys_snapshot'])

        # Execute the simulation
        execute_simulation_async(run.pk)
        messages.success(
            request,
            f"Species mapping saved. Simulation #{run.pk} is now running."
        )

        # Chain to the next pending run if there are more
        next_runs = request.POST.get('next_runs', '')
        if next_runs:
            run_ids = [r.strip() for r in next_runs.split(',') if r.strip()]
            if run_ids:
                next_pk = run_ids.pop(0)
                remaining = ','.join(run_ids)
                url = reverse('analysis:mapping-review', kwargs={'pk': next_pk})
                if remaining:
                    url += f'?next_runs={remaining}'
                return redirect(url)

        return redirect('analysis:run-detail', pk=run.pk)


class SimulationRunView(View):
    """
    Execute a simulation run (handles both AJAX and form POST).
    """
    def post(self, request, pk):
        run = get_object_or_404(SimulationRun, pk=pk)
        
        if run.status not in [SimulationStatus.PENDING, SimulationStatus.FAILED]:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': f'Cannot run simulation with status: {run.status}'
                })
            messages.error(request, f'Cannot run simulation with status: {run.status}')
            return redirect('analysis:run-detail', pk=pk)

        # Start simulation in background thread
        execute_simulation_async(run.pk)
        
        # Check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Simulation started',
                'run_id': run.pk,
            })
        
        # Regular form POST - redirect back to detail page
        messages.success(request, 'Simulation started! The page will auto-refresh when complete.')
        return redirect('analysis:run-detail', pk=pk)


class SimulationRerunView(View):
    """
    Create a new run from an existing run's model/dataset and start it.
    """
    def post(self, request, pk):
        run = get_object_or_404(SimulationRun, pk=pk)

        new_run = SimulationRun.objects.create(
            kinetic_model=run.kinetic_model,
            dataset=run.dataset,
            status=SimulationStatus.PENDING,
            triggered_by=TriggerType.MANUAL,
            triggered_by_user=request.user if request.user.is_authenticated else None,
            skip_validation=run.skip_validation,
            model_version_hash=SimulationRun.compute_model_hash(run.kinetic_model),
        )

        execute_simulation_async(new_run.pk)

        messages.success(request, 'Re-run started. The page will auto-refresh when complete.')
        return redirect('analysis:run-detail', pk=new_run.pk)


class SimulationCancelView(View):
    """
    Cancel a running or pending simulation.
    """
    def post(self, request, pk):
        run = get_object_or_404(SimulationRun, pk=pk)
        
        if run.status not in [SimulationStatus.PENDING, SimulationStatus.RUNNING, SimulationStatus.QUEUED]:
            messages.error(request, f'Cannot cancel simulation with status: {run.status}')
            return redirect('analysis:run-detail', pk=pk)
        
        run.mark_cancelled('Cancelled by user')
        messages.success(request, 'Simulation cancelled.')
        
        return redirect('analysis:run-detail', pk=pk)


class CleanupStaleRunsView(View):
    """
    Clean up stale/stuck running simulations (admin action).
    """
    def post(self, request):
        count = SimulationRun.cleanup_stale_runs(dry_run=False)
        
        if count > 0:
            messages.success(request, f'Cleaned up {count} stale simulation(s).')
        else:
            messages.info(request, 'No stale simulations found.')
        
        return redirect('analysis:run-list')


class RetryFailedRunsView(View):
    """
    Re-run all failed simulations that have no completed sibling run
    (same model + dataset pair).
    """

    @staticmethod
    def get_retryable_failed_runs():
        """Return a queryset of failed runs whose (model, dataset) pair
        has no completed run anywhere."""
        # Subquery: completed run IDs for each (model, dataset) pair
        completed_pairs = (
            SimulationRun.objects
            .filter(status=SimulationStatus.COMPLETED)
            .values_list('kinetic_model_id', 'dataset_id')
        )
        # Build set for fast membership checks
        completed_set = set(completed_pairs)

        failed_runs = SimulationRun.objects.filter(
            status=SimulationStatus.FAILED,
        ).select_related('kinetic_model', 'dataset').order_by('-created_at')

        # Deduplicate: keep only the latest failed run per (model, dataset)
        seen = set()
        retryable = []
        for run in failed_runs:
            key = (run.kinetic_model_id, run.dataset_id)
            if key not in completed_set and key not in seen:
                seen.add(key)
                retryable.append(run)

        return retryable

    def post(self, request):
        retryable = self.get_retryable_failed_runs()

        if not retryable:
            messages.info(request, 'No retryable failed simulations found.')
            return redirect('analysis:run-list')

        count = 0
        for old_run in retryable:
            new_run = SimulationRun.objects.create(
                kinetic_model=old_run.kinetic_model,
                dataset=old_run.dataset,
                status=SimulationStatus.PENDING,
                triggered_by=TriggerType.MANUAL,
                triggered_by_user=request.user if request.user.is_authenticated else None,
                skip_validation=old_run.skip_validation,
                model_version_hash=SimulationRun.compute_model_hash(old_run.kinetic_model),
            )
            execute_simulation_async(new_run.pk)
            count += 1

        messages.success(
            request,
            f'Queued {count} failed simulation{"s" if count != 1 else ""} for retry.'
        )
        return redirect('analysis:run-list')


def _parse_value_with_unit(value_str):
    """
    Parse a value string into just the number.
    
    Handles formats like:
    - '1500.0 kelvin'
    - '5390000.0 pascal'
    - '0.000254 second'
    - '(909 +/- 16) kelvin'  (with uncertainty)
    """
    if value_str is None:
        return None
    if isinstance(value_str, (int, float)):
        return float(value_str)
    
    value_str = str(value_str).strip()
    
    # Handle uncertainty format: "(909 +/- 16) kelvin" -> extract 909
    if value_str.startswith('('):
        import re
        # Match "(number +/- uncertainty) unit" or "(number) unit"
        match = re.match(r'\(([0-9.eE+-]+)', value_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    
    # Standard format: "1500.0 kelvin" -> extract 1500.0
    try:
        parts = value_str.split()
        return float(parts[0])
    except (ValueError, IndexError):
        return None


def _build_simulation_log(run: SimulationRun) -> str:
    """Build a plain-text debug log for a simulation run."""
    model = run.kinetic_model
    dataset = run.dataset

    def _file_name(field):
        if not field:
            return "—"
        try:
            return field.name or "—"
        except Exception:
            return str(field)

    lines = [
        f"Simulation Run #{run.pk}",
        f"Status: {run.status}",
        f"Created: {run.created_at}",
        f"Started: {run.started_at}",
        f"Completed: {run.completed_at}",
        "",
        "Model",
        f"  ID: {model.pk}",
        f"  Name: {model.model_name}",
        f"  Reactions file: {_file_name(getattr(model, 'chemkin_reactions_file', None))}",
        f"  Thermo file: {_file_name(getattr(model, 'chemkin_thermo_file', None))}",
        f"  Transport file: {_file_name(getattr(model, 'chemkin_transport_file', None))}",
        "",
        "Dataset",
        f"  ID: {dataset.pk}",
        f"  Short name: {dataset.short_name}",
        f"  ChemKED path: {getattr(dataset, 'chemked_file_path', '—')}",
        f"  Experiment type: {getattr(dataset, 'experiment_type', '—')}",
        "",
    f"Skip validation: {run.skip_validation}",
    f"Results dir: {run.results_dir or '—'}",
    f"Shared log file: {os.path.join(_get_simulation_log_dir(), 'simulation_runs.log')}",
        "",
        "Error message:",
        run.error_message or "—",
        "",
        "Traceback:",
        run.traceback or "—",
    ]

    return "\n".join(lines)


class SimulationLogView(View):
    """
    Download the simulation debug log as plain text.
    """
    def get(self, request, pk):
        run = get_object_or_404(SimulationRun, pk=pk)
        log_text = _build_simulation_log(run)
        response = HttpResponse(log_text, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename=simulation_run_{run.pk}_log.txt"
        return response


class SimulationDetailView(DetailView):
    """
    View details of a simulation run and its results.
    """
    model = SimulationRun
    template_name = "analysis/simulation_detail.html"
    context_object_name = "run"

    def get_queryset(self):
        return SimulationRun.objects.select_related(
            'kinetic_model',
            'dataset',
            'dataset__apparatus',
            'result',
            'triggered_by_user',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run = self.object
        context["BASE_DIR"] = getattr(settings, "BASE_DIR", "")

        if hasattr(run, 'result') and run.result:
            # Get datapoint results for plotting
            datapoints = run.result.datapoint_results.all().order_by('temperature')
            context['datapoints'] = datapoints

            # Prepare chart data
            chart_data = {
                'experimental': [],
                'simulated': [],
                'temperatures': [],
                'pressures': [],
            }
            for dp in datapoints:
                if dp.experimental_ignition_delay and dp.simulated_ignition_delay:
                    chart_data['experimental'].append(dp.experimental_ignition_delay)
                    chart_data['simulated'].append(dp.simulated_ignition_delay)
                    chart_data['temperatures'].append(dp.temperature)
                    chart_data['pressures'].append(dp.pressure)
            
            context['chart_data'] = json.dumps(chart_data)

        # Get other runs for same model-dataset pair
        context['related_runs'] = (
            SimulationRun.objects
            .filter(kinetic_model=run.kinetic_model, dataset=run.dataset)
            .exclude(pk=run.pk)
            .order_by('-created_at')[:5]
        )

        context['species_mappings'] = SpeciesMapping.objects.filter(
            kinetic_model=run.kinetic_model,
            dataset=run.dataset,
        )

        return context


class SimulationListView(ListView):
    """
    List all simulation runs with filtering.
    """
    model = SimulationRun
    template_name = "analysis/simulation_list.html"
    context_object_name = "runs"
    paginate_by = 25

    def get_queryset(self):
        qs = SimulationRun.objects.select_related(
            'kinetic_model', 'dataset', 'result'
        ).order_by('-created_at')

        # Apply filters
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        model_id = self.request.GET.get('model')
        if model_id:
            qs = qs.filter(kinetic_model_id=model_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = SimulationStatus.choices
        context['models'] = KineticModel.objects.all()
        
        # Count stale runs (running for more than 1 hour)
        from datetime import timedelta
        one_hour_ago = timezone.now() - timedelta(hours=1)
        stale_count = SimulationRun.objects.filter(
            status=SimulationStatus.RUNNING,
            started_at__lt=one_hour_ago
        ).count()
        context['stale_count'] = stale_count

        # Count retryable failed runs (failed with no completed sibling)
        context['retryable_failed_count'] = len(
            RetryFailedRunsView.get_retryable_failed_runs()
        )
        
        return context


class CoverageMatrixView(TemplateView):
    """
    Display model-dataset coverage as an interactive matrix/heatmap.
    """
    template_name = "analysis/coverage_matrix.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all models and datasets for stats
        all_models = KineticModel.objects.all()
        all_datasets = ExperimentDataset.objects.filter(experiment_type='ignition delay')
        
        context['total_models'] = all_models.count()
        context['total_datasets'] = all_datasets.count()

        # Get coverage records
        coverage_qs = ModelDatasetCoverage.objects.select_related('kinetic_model', 'dataset')
        
        # Get models and datasets that have coverage data (for the heatmap)
        models_with_coverage = list(
            KineticModel.objects
            .filter(dataset_coverage__isnull=False)
            .distinct()
            .order_by('model_name')
        )
        datasets_with_coverage = list(
            ExperimentDataset.objects
            .filter(model_coverage__isnull=False, experiment_type='ignition delay')
            .distinct()
            .order_by('chemked_file_path')
        )
        
        # If no coverage yet, show top models and datasets as placeholders
        if not models_with_coverage:
            models_with_coverage = list(all_models.order_by('model_name')[:20])
        if not datasets_with_coverage:
            datasets_with_coverage = list(all_datasets.order_by('chemked_file_path')[:20])
        
        context['models'] = models_with_coverage
        context['datasets'] = datasets_with_coverage

        # Build coverage matrix data
        coverage_data = {}
        for cov in coverage_qs:
            key = (cov.kinetic_model_id, cov.dataset_id)
            coverage_data[key] = {
                'has_run': cov.has_successful_run,
                'error_function': cov.latest_error_function,
                'is_outdated': cov.is_outdated,
            }

        # Build matrix for template
        matrix = []
        for model in models_with_coverage:
            row = {'model': model, 'cells': []}
            for dataset in datasets_with_coverage:
                key = (model.id, dataset.id)
                cell = coverage_data.get(key, {
                    'has_run': False,
                    'error_function': None,
                    'is_outdated': False,
                })
                cell['model_id'] = model.id
                cell['dataset_id'] = dataset.id
                row['cells'].append(cell)
            matrix.append(row)

        context['matrix'] = matrix

        evaluated_pairs = ModelDatasetCoverage.objects.filter(
            has_successful_run=True
        ).count()
        context['evaluated_pairs'] = evaluated_pairs
        total_pairs = context['total_models'] * context['total_datasets']
        context['coverage_percent'] = round((evaluated_pairs / total_pairs) * 100, 1) if total_pairs else 0

        context['coverage_data'] = (
            coverage_qs
            .filter(has_successful_run=True)
            .order_by('-last_evaluated_at')
        )

        # ── Prepare multi-panel visualization data ──
        import math
        import re as _re
        from collections import Counter, defaultdict

        # ---- Palette: one colour per model (extends with hash for >20) ----
        BASE_COLOURS = [
            '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
            '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
            '#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#66a61e',
            '#e6ab02', '#a6761d', '#666666', '#8dd3c7', '#fb8072',
        ]

        def _model_colour(idx):
            if idx < len(BASE_COLOURS):
                return BASE_COLOURS[idx]
            # deterministic colour from model index
            import hashlib as _hl
            h = _hl.md5(str(idx).encode()).hexdigest()
            return f'#{h[:6]}'

        model_colour = {
            m.model_name: _model_colour(i)
            for i, m in enumerate(models_with_coverage)
        }

        # ---- Fuel-folder display names ----
        # Well-known fuel name normalization for display
        _FUEL_DISPLAY_NAMES = {
            'n-butanol': 'n-Butanol', 'i-butanol': 'i-Butanol',
            't-butanol': 't-Butanol', '2-butanol': '2-Butanol',
            'n-heptane': 'n-Heptane', 'n-pentane': 'n-Pentane',
            'iso-pentane': 'iso-Pentane', 'neo-pentane': 'neo-Pentane',
            'methane': 'Methane', 'ethane': 'Ethane', 'propane': 'Propane',
            'n-butane': 'n-Butane', 'iso-butane': 'iso-Butane',
            'hydrogen': 'Hydrogen', 'methanol': 'Methanol',
            'ethanol': 'Ethanol', 'dimethyl ether': 'DME',
        }

        def _nice_fuel_name(raw: str):
            """Capitalize / prettify a fuel name for display."""
            lower = raw.lower().strip()
            if lower in _FUEL_DISPLAY_NAMES:
                return _FUEL_DISPLAY_NAMES[lower]
            # Generic: title-case but keep hyphens, e.g. "nc5h12" → "NC5H12"
            if _re.match(r'^[a-z0-9]+$', lower):
                return raw.upper()  # formula-like
            return raw.replace('_', ' ').title()

        def _fuel_for_dataset(ds):
            """Determine the fuel name for a dataset.

            Strategy (most-reliable first):
            1. Use the dataset's composition to find the primary fuel species
               (excludes O2, N2, Ar, He, etc.).
            2. If the chemked_file_path has ≥ 2 path segments, the top-level
               folder is typically the fuel (e.g. "n-heptane/Author/file.yaml").
            3. Try to extract a fuel formula from the filename itself
               (e.g. "NC5H12_JohnBugler_2016_10011004" → "NC5H12").
            4. Fall back to "Other".
            """
            # --- 1. From composition (most reliable) ---
            try:
                fuels = ds.fuel_species  # property on ExperimentDataset
                if fuels:
                    return ', '.join(sorted(fuels))
            except Exception:
                pass

            # --- 2. From folder structure ---
            if ds.chemked_file_path:
                parts = ds.chemked_file_path.split('/')
                if len(parts) >= 2:
                    # Top-level folder is the fuel name
                    return parts[0]

                # --- 3. Extract formula prefix from flat filename ---
                # e.g. "NC5H12_JohnBugler_2016_10011004" → "NC5H12"
                stem = parts[0].replace('.yaml', '')
                m = _re.match(
                    r'^([A-Za-z]*C\d+H\d+(?:[A-Za-z0-9]*)?)',
                    stem,
                )
                if m:
                    return m.group(1).upper()

            return "Other"

        def _dataset_short_label(ds):
            """Concise per-dataset label (author + condition)."""
            if not ds.chemked_file_path:
                return f"DS {ds.pk}"
            parts = ds.chemked_file_path.split("/")
            stem = parts[-1].replace(".yaml", "") if parts else ""
            if len(parts) >= 3:
                af = parts[-2]
                m = _re.search(r'-(\d+)$', stem)
                return f"{af} #{m.group(1)}" if m else af
            m_crv = _re.match(r'CRV_([A-Za-z]+)_(\d{4})', stem)
            if m_crv:
                return f"{m_crv.group(1)} {m_crv.group(2)} CRV"
            m = _re.match(r'([A-Za-z]+)_(\d{4})_(.+)', stem)
            if m:
                author, year, rest = m.group(1), m.group(2), m.group(3)
                phi = _re.search(r'phi[_]?([\d.]+)', rest)
                atm = _re.search(r'(\d+)atm', rest)
                conc = _re.search(r'[_x](\d+\.\d+)$', rest)
                if not conc:
                    conc = _re.search(r'x[A-Za-z\-]+([\d.]+)$', rest)
                conds = []
                if phi:  conds.append(f"φ={phi.group(1)}")
                if atm:  conds.append(f"{atm.group(1)}atm")
                if conc: conds.append(f"x={conc.group(1)}")
                tag = ", ".join(conds) if conds else rest[:15]
                return f"{author} {year} ({tag})"
            return stem[:30]

        # ---- Group datasets by fuel ----
        fuel_datasets = defaultdict(list)
        for ds in datasets_with_coverage:
            fuel_datasets[_fuel_for_dataset(ds)].append(
                (ds, _dataset_short_label(ds))
            )
        # Disambiguate labels within each fuel group
        for fuel, pairs in fuel_datasets.items():
            labels = [lbl for _, lbl in pairs]
            lc = Counter(labels)
            seen: dict = {}
            for i, (ds, lbl) in enumerate(pairs):
                if lc[lbl] > 1:
                    seen[lbl] = seen.get(lbl, 0) + 1
                    pairs[i] = (ds, f"{lbl} [{seen[lbl]}]")

        fuel_order = sorted(fuel_datasets.keys())

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. MODEL × FUEL HEATMAP  (compact — scales to 100+ models)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        fuel_labels = [_nice_fuel_name(f) for f in fuel_order]
        model_labels = [m.model_name for m in models_with_coverage]

        # Build aggregated stats: per (model, fuel) → avg error
        model_fuel_stats = {}   # (model_name, fuel_folder) → {avg, best, count, errors}
        for model in models_with_coverage:
            for fuel in fuel_order:
                errors = []
                for ds, _ in fuel_datasets[fuel]:
                    key = (model.id, ds.id)
                    cov = coverage_data.get(key)
                    if cov and cov['has_run'] and cov['error_function'] is not None:
                        errors.append(cov['error_function'])
                if errors:
                    model_fuel_stats[(model.model_name, fuel)] = {
                        'avg': sum(errors) / len(errors),
                        'best': min(errors),
                        'worst': max(errors),
                        'count': len(errors),
                        'total': len(fuel_datasets[fuel]),
                    }

        # Heatmap z-values (log10 of avg error) and hover text
        hm_z = []
        hm_text = []
        for model in models_with_coverage:
            row_z = []
            row_t = []
            for fuel in fuel_order:
                stats = model_fuel_stats.get((model.model_name, fuel))
                nice = _nice_fuel_name(fuel)
                if stats:
                    log_val = math.log10(max(stats['avg'], 0.01))
                    row_z.append(log_val)
                    row_t.append(
                        f"<b>{model.model_name}</b><br>"
                        f"{nice}<br>"
                        f"Avg Error: {stats['avg']:.1f}<br>"
                        f"Best: {stats['best']:.2f}<br>"
                        f"Datasets: {stats['count']}/{stats['total']}"
                    )
                else:
                    row_z.append(None)
                    row_t.append("")
            hm_z.append(row_z)
            hm_text.append(row_t)

        colorscale = [
            [0.0, '#198754'],  [0.15, '#28a745'],
            [0.35, '#ffc107'], [0.55, '#fd7e14'],
            [0.75, '#dc3545'], [1.0, '#721c24'],
        ]
        n_models = len(models_with_coverage)
        hm_height = max(300, n_models * 36 + 120)

        context['heatmap_json'] = json.dumps({
            'data': [{
                'type': 'heatmap',
                'z': hm_z,
                'x': fuel_labels,
                'y': model_labels,
                'text': hm_text,
                'hoverinfo': 'text',
                'hoverongaps': False,
                'colorscale': colorscale,
                'zmin': -2, 'zmax': 5,
                'xgap': 3, 'ygap': 3,
                'colorbar': {
                    'title': 'Log₁₀(Avg Error)',
                    'tickvals': [-2, -1, 0, 1, 2, 3, 4, 5],
                    'ticktext': ['0.01', '0.1', '1', '10', '100', '1k', '10k', '100k'],
                    'len': 0.9,
                },
            }],
            'layout': {
                'margin': {'l': 200, 'r': 100, 't': 10, 'b': 80},
                'xaxis': {'type': 'category', 'tickangle': -30, 'side': 'bottom'},
                'yaxis': {'type': 'category', 'autorange': 'reversed', 'automargin': True},
                'height': hm_height,
                'plot_bgcolor': '#fff',
            },
        })

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. MODEL RANKING TABLE (for template, no chart)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        model_summaries = []
        for model in models_with_coverage:
            all_errors = []
            fuel_breakdown = []
            for fuel in fuel_order:
                stats = model_fuel_stats.get((model.model_name, fuel))
                nice = _nice_fuel_name(fuel)
                if stats:
                    fuel_breakdown.append({
                        'fuel': nice,
                        'avg': stats['avg'],
                        'best': stats['best'],
                        'worst': stats['worst'],
                        'count': stats['count'],
                        'total': stats['total'],
                        'pct': round(stats['count'] / stats['total'] * 100),
                    })
                    all_errors.extend([stats['avg']] * stats['count'])

            model_summaries.append({
                'name': model.model_name,
                'colour': model_colour[model.model_name],
                'total_datasets': len(all_errors),
                'avg_error': sum(all_errors) / len(all_errors) if all_errors else None,
                'best_error': min(all_errors) if all_errors else None,
                'fuels': fuel_breakdown,
            })
        # Sort by avg error (best first)
        model_summaries.sort(key=lambda s: s['avg_error'] if s['avg_error'] is not None else 1e9)
        context['model_summaries'] = model_summaries

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. PER-FUEL DRILL-DOWN DATA  (JSON for JS-driven tabs)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        drill_down = {}   # fuel_folder → { traces, layout }
        for fuel in fuel_order:
            pairs = fuel_datasets[fuel]
            ds_labels = [lbl for _, lbl in pairs]
            nice = _nice_fuel_name(fuel)

            traces = []
            for model in models_with_coverage:
                y_vals = []
                hovers = []
                for ds, lbl in pairs:
                    key = (model.id, ds.id)
                    cov = coverage_data.get(key)
                    if cov and cov['has_run'] and cov['error_function'] is not None:
                        val = cov['error_function']
                        y_vals.append(val)
                        hovers.append(
                            f"<b>{model.model_name}</b><br>"
                            f"{lbl}<br>"
                            f"Error: {val:.2f}"
                        )
                    else:
                        y_vals.append(None)
                        hovers.append("")
                traces.append({
                    'type': 'bar',
                    'name': model.model_name,
                    'x': ds_labels,
                    'y': y_vals,
                    'text': hovers,
                    'hoverinfo': 'text',
                    'marker': {'color': model_colour[model.model_name]},
                })

            n_ds = len(pairs)
            n_m = len(models_with_coverage)
            chart_w = max(400, n_ds * n_m * 18 + 120)

            drill_down[fuel] = {
                'data': traces,
                'layout': {
                    'barmode': 'group',
                    'yaxis': {'title': 'Error Function', 'type': 'log', 'gridcolor': '#eee'},
                    'xaxis': {'tickangle': -40, 'tickfont': {'size': 9}, 'type': 'category'},
                    'margin': {'l': 60, 'r': 20, 't': 10, 'b': 120},
                    'height': 380,
                    'width': chart_w,
                    'legend': {'orientation': 'h', 'y': 1.08, 'x': 0.5, 'xanchor': 'center'},
                    'plot_bgcolor': '#fff',
                    'paper_bgcolor': '#fff',
                },
            }

        context['fuel_tabs'] = [
            {'key': f, 'label': _nice_fuel_name(f), 'count': len(fuel_datasets[f])}
            for f in fuel_order
        ]
        context['drill_down_json'] = json.dumps(drill_down)

        return context


class CompareModelsView(TemplateView):
    """
    Compare multiple models against the same dataset(s).
    """
    template_name = "analysis/compare_models.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        model_ids = self.request.GET.getlist('models')
        dataset_id = self.request.GET.get('dataset')

        context['all_models'] = KineticModel.objects.all()
        context['all_datasets'] = ExperimentDataset.objects.filter(
            experiment_type='ignition delay'
        )
        
        # Pass selected IDs to template for form state
        context['selected_model_ids'] = model_ids
        context['selected_dataset_id'] = dataset_id

        if model_ids and dataset_id:
            models = KineticModel.objects.filter(id__in=model_ids)
            dataset = get_object_or_404(ExperimentDataset, pk=dataset_id)

            context['selected_models'] = models
            context['selected_dataset'] = dataset

            # Get results for comparison
            comparison_data = []
            for model in models:
                run = (
                    SimulationRun.objects
                    .filter(
                        kinetic_model=model,
                        dataset=dataset,
                        status=SimulationStatus.COMPLETED
                    )
                    .select_related('result')
                    .order_by('-completed_at')
                    .first()
                )
                if run and hasattr(run, 'result'):
                    comparison_data.append({
                        'model': model,
                        'run': run,
                        'result': run.result,
                        'datapoints': list(run.result.datapoint_results.all()),
                    })

            context['comparison_data'] = comparison_data

            # Prepare chart data for comparison plot
            chart_data = {'models': []}
            for item in comparison_data:
                model_data = {
                    'name': item['model'].model_name,
                    'experimental': [],
                    'simulated': [],
                    'temperatures': [],
                }
                for dp in item['datapoints']:
                    if dp.experimental_ignition_delay and dp.simulated_ignition_delay:
                        model_data['experimental'].append(dp.experimental_ignition_delay)
                        model_data['simulated'].append(dp.simulated_ignition_delay)
                        model_data['temperatures'].append(dp.temperature)
                chart_data['models'].append(model_data)

            context['chart_data'] = json.dumps(chart_data)

        return context



# API Views for AJAX
class DatasetsByFuelView(View):
    """
    API endpoint to get datasets filtered by fuel species.
    Optimized for performance with annotated counts.
    """
    def get(self, request):
        from django.db.models import Count
        
        keyword = (request.GET.get('q') or request.GET.get('keyword') or '').strip()
        smiles = (request.GET.get('smiles') or '').strip()
        inchi = (request.GET.get('inchi') or '').strip()
        experiment_type = (request.GET.get('experiment_type') or '').strip()
        apparatus_kind = (request.GET.get('apparatus_kind') or '').strip()
        target = (request.GET.get('target') or '').strip()
        limit = int(request.GET.get('limit') or 200)

        # Start with annotated count to avoid N+1 queries
        dataset_qs = (
            ExperimentDataset.objects
            .select_related('common_properties', 'apparatus')
            .annotate(datapoints_count=Count('datapoints'))
            .order_by('chemked_file_path')
        )

        if experiment_type:
            dataset_qs = dataset_qs.filter(experiment_type__iexact=experiment_type)
        if apparatus_kind:
            dataset_qs = dataset_qs.filter(apparatus__kind__iexact=apparatus_kind)
        if target:
            dataset_qs = dataset_qs.filter(common_properties__ignition_target__iexact=target)

        if keyword or smiles or inchi:
            species_query = Q()
            if keyword:
                species_query |= Q(species_name__icontains=keyword)
                species_query |= Q(chem_name__icontains=keyword)
                species_query |= Q(cas__icontains=keyword)
                species_query |= Q(inchi__icontains=keyword)
                species_query |= Q(smiles__icontains=keyword)
            if smiles:
                species_query |= Q(smiles=smiles)
            if inchi:
                species_query |= Q(inchi__icontains=inchi)

            dataset_ids = list(
                CompositionSpecies.objects
                .filter(species_query)
                .values_list('composition__datapoints__dataset_id', flat=True)
                .distinct()[:500]  # Limit subquery results
            )

            # Filter by species or file path
            dataset_qs = dataset_qs.filter(
                Q(id__in=dataset_ids)
                | Q(chemked_file_path__icontains=keyword)
            )

        # Fetch limited results
        datasets = []
        for dataset in dataset_qs[:limit]:
            # Get apparatus kind safely
            apparatus_kind_val = ''
            try:
                if dataset.apparatus:
                    apparatus_kind_val = dataset.apparatus.kind or ''
            except Exception:
                pass
            
            # Get fuel species safely
            fuel_species = []
            try:
                if hasattr(dataset, 'fuel_species'):
                    fuel_species = dataset.fuel_species or []
            except Exception:
                pass
            
            # Get short_name safely (it's a property)
            short_name = ''
            try:
                if hasattr(dataset, 'short_name'):
                    short_name = dataset.short_name or ''
            except Exception:
                pass
            if not short_name and dataset.chemked_file_path:
                import os
                short_name = os.path.basename(dataset.chemked_file_path).replace('.yaml', '')
            
            # Get ignition_target safely
            ignition_target = ''
            try:
                if dataset.common_properties:
                    ignition_target = dataset.common_properties.ignition_target or ''
            except Exception:
                pass
            
            datasets.append({
                'id': dataset.id,
                'short_name': short_name,
                'experiment_type': dataset.experiment_type or '',
                'apparatus_kind': apparatus_kind_val,
                'fuel_species': fuel_species,
                'datapoints_count': dataset.datapoints_count,  # Use annotated value
                'ignition_target': ignition_target,
                'chemked_file_path': dataset.chemked_file_path or '',
            })

        return JsonResponse({'datasets': datasets})


class ModelsByKeywordView(View):
    """
    API endpoint to get kinetic models filtered by keyword.
    Fast query - no expensive counts.
    """
    def get(self, request):
        keyword = (request.GET.get('q') or '').strip()
        limit = int(request.GET.get('limit') or 200)

        qs = KineticModel.objects.all().order_by('model_name')
        if keyword:
            qs = qs.filter(model_name__icontains=keyword)

        # Fast query - just basic fields, no joins
        models = list(
            qs.values('id', 'model_name', 'prime_id')[:limit]
        )

        return JsonResponse({'models': models})


class ModelCountsView(View):
    """
    API endpoint to get species/reaction counts for a set of model IDs.
    Keeps the main models API fast by computing counts on demand.
    """
    def get(self, request):
        from django.db.models import Count

        ids_param = (request.GET.get('ids') or '').strip()
        if not ids_param:
            return JsonResponse({'counts': {}})

        try:
            raw_ids = [int(value) for value in ids_param.split(',') if value.strip().isdigit()]
        except ValueError:
            raw_ids = []

        if not raw_ids:
            return JsonResponse({'counts': {}})

        # Limit to a reasonable batch size
        model_ids = raw_ids[:200]

        counts_qs = (
            KineticModel.objects
            .filter(id__in=model_ids)
            .annotate(
                species_count=Count('species', distinct=True),
                reaction_count=Count('kinetics', distinct=True)
            )
            .values('id', 'species_count', 'reaction_count')
        )

        counts = {
            str(row['id']): {
                'species_count': row['species_count'],
                'reaction_count': row['reaction_count'],
            }
            for row in counts_qs
        }

        return JsonResponse({'counts': counts})


class SimulationStatusView(View):
    """
    API endpoint to get the current status of a simulation run.
    Used for auto-refresh polling on the detail page.
    """
    def get(self, request, pk):
        try:
            run = SimulationRun.objects.get(pk=pk)
        except SimulationRun.DoesNotExist:
            return JsonResponse({'error': 'Run not found'}, status=404)

        data = {
            'id': run.id,
            'status': run.status,
            'created_at': run.created_at.isoformat() if run.created_at else None,
            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
            'error_message': run.error_message or '',
        }

        # Include result summary if completed
        if run.status == 'completed' and hasattr(run, 'result') and run.result:
            data['result'] = {
                'average_error_function': float(run.result.average_error_function) if run.result.average_error_function else None,
                'std_error_function': float(run.result.std_error_function) if run.result.std_error_function else None,
                'datapoints_count': run.result.datapoint_results.count() if hasattr(run.result, 'datapoint_results') else 0,
            }

        return JsonResponse(data)


# ===========================================================================
# Fuel-Model Compatibility Map Views
# ===========================================================================

class FuelMapView(TemplateView):
    """
    Main Fuel-Model Compatibility Map page.
    Lists fuel species with dataset/model counts and search.
    """
    template_name = "analysis/fuel_map.html"

    def get_context_data(self, **kwargs):
        from .models import FuelSpecies, FuelGroup, FuelModelCompatibility

        context = super().get_context_data(**kwargs)

        search = self.request.GET.get("q", "").strip()
        group_id = self.request.GET.get("group", "").strip()
        sort = self.request.GET.get("sort", "datasets")  # datasets | models | name

        # Base queryset
        fuels_qs = FuelSpecies.objects.select_related("group")

        if search:
            fuels_qs = fuels_qs.filter(
                Q(common_name__icontains=search)
                | Q(smiles__icontains=search)
                | Q(formula__icontains=search)
                | Q(inchi__icontains=search)
                | Q(name_variants__contains=search)
            )
            context["search_query"] = search

        if group_id:
            fuels_qs = fuels_qs.filter(group_id=group_id)
            context["active_group_id"] = int(group_id)

        # Sorting
        if sort == "models":
            fuels_qs = fuels_qs.order_by("-compatible_model_count", "-dataset_count")
        elif sort == "name":
            fuels_qs = fuels_qs.order_by("common_name")
        else:
            fuels_qs = fuels_qs.order_by("-dataset_count", "-compatible_model_count")

        context["fuels"] = fuels_qs
        context["sort"] = sort

        # Groups sidebar
        context["fuel_groups"] = FuelGroup.objects.annotate(
            fuel_count=Count("fuels")
        ).filter(fuel_count__gt=0).order_by("display_order", "name")

        # Summary stats
        context["total_fuels"] = FuelSpecies.objects.count()
        context["total_compatible_pairs"] = FuelModelCompatibility.objects.filter(
            is_compatible=True
        ).count()
        context["total_models_in_map"] = (
            FuelModelCompatibility.objects.filter(is_compatible=True)
            .values("kinetic_model").distinct().count()
        )

        return context


class FuelDetailView(TemplateView):
    """
    Intermediate compatibility detail page for a specific fuel.
    Shows all compatible models, species mapping preview for each,
    and links to run simulations.
    """
    template_name = "analysis/fuel_detail.html"

    def get_context_data(self, **kwargs):
        from .models import FuelSpecies, FuelModelCompatibility

        context = super().get_context_data(**kwargs)
        fuel_id = self.kwargs["pk"]
        fuel = get_object_or_404(FuelSpecies, pk=fuel_id)
        context["fuel"] = fuel

        # Get all compatibility records for this fuel
        compat_qs = (
            FuelModelCompatibility.objects
            .filter(fuel=fuel)
            .select_related("kinetic_model", "latest_coverage")
            .order_by("-is_compatible", "kinetic_model__model_name")
        )

        # Split into compatible and incompatible
        compatible = []
        incompatible = []
        for c in compat_qs:
            if c.is_compatible:
                compatible.append(c)
            else:
                incompatible.append(c)

        context["compatible_models"] = compatible
        context["incompatible_models"] = incompatible
        context["compatible_count"] = len(compatible)
        context["incompatible_count"] = len(incompatible)

        # Datasets that use this fuel
        dataset_ids = set()
        # Find datasets through CompositionSpecies
        from chemked_database.models import CompositionSpecies as CS
        cs_qs = CS.objects.filter(
            Q(inchi=fuel.inchi) | Q(smiles=fuel.smiles)
        ).exclude(
            species_name__in=['O2', 'N2', 'Ar', 'He', 'CO2', 'H2O']
        ).select_related("composition")

        for cs in cs_qs:
            if cs.composition_id:
                # Through datapoints
                dp_datasets = cs.composition.datapoints.values_list(
                    "dataset_id", flat=True
                )
                dataset_ids.update(dp_datasets)
                # Through common_properties (OneToOne reverse)
                try:
                    cp = cs.composition.common_properties
                    if cp:
                        dataset_ids.add(cp.dataset_id)
                except Exception:
                    pass

        context["datasets"] = (
            ExperimentDataset.objects
            .filter(pk__in=dataset_ids)
            .order_by("chemked_file_path")
        )
        context["dataset_count"] = len(dataset_ids)

        return context


class FuelModelMappingPreviewView(View):
    """
    API endpoint: return the species mapping snapshot for a fuel × model pair.
    Used for AJAX expand-on-click in the fuel detail page.

    The snapshot is stored as a list of per-dataset entries (new format) or
    a flat dict (legacy format from before the per-dataset refactor).
    """
    def get(self, request, fuel_pk, model_pk):
        from .models import FuelSpecies, FuelModelCompatibility

        try:
            compat = FuelModelCompatibility.objects.get(
                fuel_id=fuel_pk, kinetic_model_id=model_pk
            )
        except FuelModelCompatibility.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        snapshot = compat.species_mapping_snapshot

        # New format: list of per-dataset dicts
        if isinstance(snapshot, list):
            datasets = snapshot
        elif isinstance(snapshot, dict) and snapshot:
            # Legacy format: flat {species_name: info_dict} — wrap in one
            # pseudo-dataset for backward compat
            rows = []
            for ds_name, info in snapshot.items():
                if isinstance(info, dict):
                    rows.append({
                        "name": ds_name,
                        "model_name": info.get("model_name", ""),
                        "method": info.get("method", ""),
                        "smiles": info.get("smiles", ""),
                        "matched": bool(info.get("model_name")),
                    })
                else:
                    rows.append({
                        "name": ds_name,
                        "model_name": info if info else "",
                        "method": "unknown",
                        "smiles": "",
                        "matched": bool(info),
                    })
            datasets = [{
                "dataset_id": None,
                "dataset_name": "All datasets (legacy)",
                "species": rows,
                "matched_count": sum(1 for r in rows if r["matched"]),
                "total_count": len(rows),
            }]
        else:
            datasets = []

        return JsonResponse({
            "fuel": str(compat.fuel),
            "fuel_pk": compat.fuel_id,
            "model": compat.kinetic_model.model_name,
            "model_pk": compat.kinetic_model_id,
            "is_compatible": compat.is_compatible,
            "matched_species": compat.matched_model_species,
            "datasets": datasets,
        })


class RebuildFuelMapView(SiteLoginRequiredMixin, View):
    """Trigger a fuel map rebuild via the UI."""

    def post(self, request):
        from .services.fuel_model_map import rebuild_fuel_map

        try:
            stats = rebuild_fuel_map()
            messages.success(
                request,
                f"Fuel map rebuilt: {stats['fuels_found']} fuels, "
                f"{stats['compatible_pairs']} compatible pairs."
            )
        except Exception as e:
            logger.exception("Fuel map rebuild failed")
            messages.error(request, f"Rebuild failed: {e}")

        return redirect("analysis:fuel-map")
