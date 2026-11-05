"""
URL configuration for the importer dashboard
"""

from django.urls import path
from . import draft_views, views

app_name = 'importer_dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard_index, name='index'),
    
    # Job management
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('job/<int:job_id>/start/', views.job_start, name='job_start'),
    path('job/<int:job_id>/kill/', views.job_kill, name='job_kill'),
    path('job/<int:job_id>/log/', views.job_log_view, name='job_log'),
    path('job/<int:job_id>/error-log/', views.job_error_log_view, name='job_error_log'),
    path('job/<int:job_id>/draft/discard/', draft_views.draft_discard, name='draft_discard'),
    path('job/<int:job_id>/draft/pull-request/', draft_views.draft_pull_request, name='draft_pull_request'),
    path('job/<int:job_id>/draft/open/', draft_views.draft_open, name='draft_open'),
    path('job/<int:job_id>/files/', draft_views.draft_files, name='draft_files'),
    path('job/<int:job_id>/files/<path:name>', draft_views.draft_file_edit, name='draft_file_edit'),
    path('github/connect/', draft_views.github_connect, name='github_connect'),
    path('github/callback/', draft_views.github_callback, name='github_callback'),
    path('github/disconnect/', draft_views.github_disconnect, name='github_disconnect'),
    
    # Dashboard actions
    path('refresh-jobs/', views.refresh_jobs, name='refresh_jobs'),
    path('refresh-progress/', views.refresh_progress, name='refresh_progress'),
    path('reconnect/', views.reconnect, name='reconnect'),
    path('git-pull/', views.git_pull, name='git_pull'),
    path('settings/', views.settings_view, name='settings'),
    
    # Log streaming
    path('logs/stream/', views.stream_logs, name='stream_logs'),
    path('logs/get/', views.get_logs, name='get_logs'),
    path('clear-logs/', views.clear_logs, name='clear_logs'),
    
    # API endpoints
    path('api/jobs-stats/', views.jobs_stats_api, name='jobs_stats_api'),
]
