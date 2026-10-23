"""
Analysis Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    SimulationRun,
    SimulationResult,
    DatapointResult,
    SpeciesMapping,
    ModelDatasetCoverage,
    SimulationStatus,
)


class SimulationResultInline(admin.StackedInline):
    model = SimulationResult
    readonly_fields = [
        'average_error_function',
        'average_deviation_function',
        'num_datapoints',
        'num_successful',
        'num_failed',
    ]
    extra = 0


@admin.register(SimulationRun)
class SimulationRunAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'kinetic_model',
        'dataset_short',
        'status_badge',
        'error_function_display',
        'triggered_by',
        'created_at',
        'duration_display',
    ]
    list_filter = ['status', 'triggered_by', 'created_at']
    search_fields = ['kinetic_model__model_name', 'dataset__chemked_file_path']
    raw_id_fields = ['kinetic_model', 'dataset', 'triggered_by_user']
    readonly_fields = ['model_version_hash', 'created_at', 'started_at', 'completed_at']
    inlines = [SimulationResultInline]

    def dataset_short(self, obj):
        return obj.dataset.short_name if obj.dataset else '-'
    dataset_short.short_description = 'Dataset'

    def status_badge(self, obj):
        colors = {
            SimulationStatus.PENDING: '#6c757d',
            SimulationStatus.QUEUED: '#17a2b8',
            SimulationStatus.RUNNING: '#ffc107',
            SimulationStatus.COMPLETED: '#28a745',
            SimulationStatus.FAILED: '#dc3545',
            SimulationStatus.CANCELLED: '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def error_function_display(self, obj):
        if hasattr(obj, 'result') and obj.result and obj.result.average_error_function:
            return f"{obj.result.average_error_function:.2f}"
        return '-'
    error_function_display.short_description = 'Error Function'

    def duration_display(self, obj):
        if obj.duration:
            return f"{obj.duration:.1f}s"
        return '-'
    duration_display.short_description = 'Duration'


@admin.register(SimulationResult)
class SimulationResultAdmin(admin.ModelAdmin):
    list_display = [
        'simulation_run',
        'average_error_function',
        'average_deviation_function',
        'num_datapoints',
        'num_successful',
    ]
    raw_id_fields = ['simulation_run']


@admin.register(DatapointResult)
class DatapointResultAdmin(admin.ModelAdmin):
    list_display = [
        'simulation_result',
        'temperature',
        'pressure_bar',
        'experimental_ignition_delay',
        'simulated_ignition_delay',
        'success',
    ]
    list_filter = ['success']
    raw_id_fields = ['simulation_result', 'datapoint']

    def pressure_bar(self, obj):
        return f"{obj.pressure / 1e5:.2f} bar"
    pressure_bar.short_description = 'Pressure'


@admin.register(SpeciesMapping)
class SpeciesMappingAdmin(admin.ModelAdmin):
    list_display = [
        'kinetic_model',
        'dataset_display',
        'dataset_species_name',
        'model_species_name',
        'mapping_method',
        'confidence_badge',
        'is_manual_override',
    ]
    list_display_links = ['dataset_species_name']
    list_editable = ['model_species_name', 'is_manual_override']
    list_filter = ['mapping_method', 'is_manual_override', 'kinetic_model']
    search_fields = ['dataset_species_name', 'model_species_name']
    raw_id_fields = ['kinetic_model', 'dataset', 'override_by']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Mapping', {
            'fields': (
                'kinetic_model', 'dataset',
                'dataset_species_name', 'model_species_name',
            ),
        }),
        ('Match info', {
            'fields': ('mapping_method', 'confidence', 'smiles', 'inchi'),
        }),
        ('Manual override', {
            'fields': ('is_manual_override', 'override_by', 'override_reason'),
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def dataset_display(self, obj):
        if obj.dataset:
            return obj.dataset.short_name
        return format_html('<span class="text-muted">All datasets</span>')
    dataset_display.short_description = 'Dataset'

    def confidence_badge(self, obj):
        if obj.confidence >= 0.9:
            color = '#28a745'
        elif obj.confidence >= 0.6:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{:.0%}</span>',
            color, obj.confidence
        )
    confidence_badge.short_description = 'Confidence'

    def save_model(self, request, obj, form, change):
        """Auto-set override metadata when admin edits a mapping."""
        if change and 'model_species_name' in form.changed_data:
            obj.is_manual_override = True
            obj.mapping_method = 'manual'
            obj.confidence = 1.0
            obj.override_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ModelDatasetCoverage)
class ModelDatasetCoverageAdmin(admin.ModelAdmin):
    list_display = [
        'kinetic_model',
        'dataset_short',
        'has_successful_run',
        'is_outdated',
        'needs_rerun',
        'latest_error_function',
        'total_runs',
        'last_evaluated_at',
    ]
    list_filter = ['has_successful_run', 'is_outdated', 'needs_rerun']
    search_fields = ['kinetic_model__model_name', 'dataset__chemked_file_path']
    raw_id_fields = ['kinetic_model', 'dataset', 'latest_run']

    def dataset_short(self, obj):
        return obj.dataset.short_name if obj.dataset else '-'
    dataset_short.short_description = 'Dataset'
