"""
ChemKED Database URL Configuration
"""

from django.urls import path
from . import views

app_name = "chemked_database"

urlpatterns = [
    # Home / Overview
    path("", views.ChemKEDHomeView.as_view(), name="home"),

    # Datasets
    path("datasets/", views.DatasetListView.as_view(), name="dataset-list"),
    path("dataset/<int:pk>/", views.DatasetDetailView.as_view(), name="dataset-detail"),
    
    # Dataset Creation & Import
    path("dataset/create/", views.DatasetCreateWizardView.as_view(), name="dataset-create"),
    path("dataset/upload/", views.DatasetUploadView.as_view(), name="dataset-upload"),
    path("dataset/upload/process/", views.DatasetProcessView.as_view(), name="dataset-process"),
    path("dataset/clear/", views.ClearWizardView.as_view(), name="dataset-clear-wizard"),
    
    # AJAX helpers
    path("verify-orcid/", views.verify_orcid_view, name="verify-orcid"),
    path("verify-github/", views.verify_github_username_view, name="verify-github"),

    # Submission status
    path("submission/<int:pk>/", views.SubmissionStatusView.as_view(), name="submission-status"),
    path("submission/<int:pk>/check-runs/", views.SubmissionCheckRunsView.as_view(), name="submission-check-runs"),

    # Dataset Export
    path("dataset/<int:pk>/export/", views.DatasetExportView.as_view(), name="dataset-export"),

    # Datapoints
    path("datapoint/<int:pk>/", views.DatapointDetailView.as_view(), name="datapoint-detail"),

    # Species
    path("species/", views.SpeciesSearchView.as_view(), name="species-search"),
    path("species/<str:species_name>/", views.SpeciesDatapointsView.as_view(), name="species-datapoints"),

    # Apparatus
    path("apparatus/", views.ApparatusListView.as_view(), name="apparatus-list"),
]
