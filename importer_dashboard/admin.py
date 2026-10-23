"""
Django admin configuration for the importer dashboard
"""

from django.contrib import admin
from .models import ImportJobConfig, ClusterJob, JobLog


@admin.register(ImportJobConfig)
class ImportJobConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'slurm_partition', 'slurm_memory', 'slurm_time_limit', 'updated_at')
    list_filter = ('is_default', 'slurm_partition')
    search_fields = ('name', 'ssh_host')
    readonly_fields = ('created_at', 'updated_at', 'slurm_string')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_default')
        }),
        ('SSH Configuration', {
            'fields': ('ssh_host', 'ssh_port', 'root_path')
        }),
        ('SLURM Configuration', {
            'fields': ('slurm_partition', 'slurm_time_limit', 'slurm_memory', 
                      'slurm_extra_args', 'slurm_string')
        }),
        ('Environment', {
            'fields': ('conda_env_name', 'rmg_py_path')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class JobLogInline(admin.TabularInline):
    model = JobLog
    extra = 0
    readonly_fields = ('timestamp', 'log_type', 'message')
    fields = ('timestamp', 'log_type', 'message')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ClusterJob)
class ClusterJobAdmin(admin.ModelAdmin):
    list_display = ('name', 'port', 'status', 'slurm_job_id', 'host', 
                   'progress_percentage', 'started_by', 'updated_at')
    list_filter = ('status', 'config', 'started_by')
    search_fields = ('name', 'port', 'slurm_job_id', 'host')
    readonly_fields = ('progress_percentage', 'created_at', 'updated_at', 
                      'started_at', 'completed_at')
    
    fieldsets = (
        ('Job Information', {
            'fields': ('name', 'port', 'status', 'slurm_job_id', 'host')
        }),
        ('Configuration', {
            'fields': ('config',)
        }),
        ('Progress', {
            'fields': (
                'progress_percentage',
                ('total_species', 'identified_species', 'processed_species', 'confirmed_species'),
                ('total_reactions', 'unmatched_reactions'),
            )
        }),
        ('Logs', {
            'fields': ('last_log_update', 'last_error_update')
        }),
        ('User Tracking', {
            'fields': ('started_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [JobLogInline]
    
    actions = ['mark_as_pending', 'mark_as_running', 'mark_as_completed', 'mark_as_failed']
    
    def mark_as_pending(self, request, queryset):
        queryset.update(status='pending')
    mark_as_pending.short_description = "Mark selected jobs as pending"
    
    def mark_as_running(self, request, queryset):
        queryset.update(status='running')
    mark_as_running.short_description = "Mark selected jobs as running"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected jobs as completed"
    
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
    mark_as_failed.short_description = "Mark selected jobs as failed"


@admin.register(JobLog)
class JobLogAdmin(admin.ModelAdmin):
    list_display = ('job', 'log_type', 'message_preview', 'timestamp')
    list_filter = ('log_type', 'job__config')
    search_fields = ('message', 'job__name')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'
