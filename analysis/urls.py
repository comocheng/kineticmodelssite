"""
Analysis URL Configuration
"""

from django.urls import path
from . import views

app_name = "analysis"

urlpatterns = [
    # Dashboard
    path("", views.AnalysisDashboardView.as_view(), name="dashboard"),

    # Simulation runs
    path("run/create/", views.SimulationCreateView.as_view(), name="run-create"),
    path("run/<int:pk>/", views.SimulationDetailView.as_view(), name="run-detail"),
    path("run/<int:pk>/mapping-review/", views.SpeciesMappingReviewView.as_view(), name="mapping-review"),
    path("run/<int:pk>/execute/", views.SimulationRunView.as_view(), name="run-execute"),
    path("run/<int:pk>/rerun/", views.SimulationRerunView.as_view(), name="run-rerun"),
    path("run/<int:pk>/cancel/", views.SimulationCancelView.as_view(), name="run-cancel"),
    path("runs/", views.SimulationListView.as_view(), name="run-list"),
    path("runs/cleanup-stale/", views.CleanupStaleRunsView.as_view(), name="cleanup-stale"),
    path("runs/retry-failed/", views.RetryFailedRunsView.as_view(), name="retry-failed"),

    # Coverage & comparison
    path("coverage/", views.CoverageMatrixView.as_view(), name="coverage-matrix"),
    path("compare/", views.CompareModelsView.as_view(), name="compare-models"),

    # Fuel-Model Compatibility Map
    path("fuel-map/", views.FuelMapView.as_view(), name="fuel-map"),
    path("fuel-map/<int:pk>/", views.FuelDetailView.as_view(), name="fuel-detail"),
    path("fuel-map/rebuild/", views.RebuildFuelMapView.as_view(), name="fuel-map-rebuild"),

    # API endpoints
    path("api/datasets-by-fuel/", views.DatasetsByFuelView.as_view(), name="api-datasets-by-fuel"),
    path("api/models/", views.ModelsByKeywordView.as_view(), name="api-models-by-keyword"),
    path("api/model-counts/", views.ModelCountsView.as_view(), name="api-model-counts"),
    path("api/run/<int:pk>/status/", views.SimulationStatusView.as_view(), name="api-run-status"),
    path("api/run/<int:pk>/log/", views.SimulationLogView.as_view(), name="api-run-log"),
    path(
        "api/fuel-map/<int:fuel_pk>/model/<int:model_pk>/mapping/",
        views.FuelModelMappingPreviewView.as_view(),
        name="api-fuel-model-mapping",
    ),
]
