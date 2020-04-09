from django.urls import path
from django_filters.views import FilterView

from . import views

urlpatterns = [
    path(r'', views.BaseView.as_view(), name="home"),
    path(r"species_search/", FilterView.as_view(filterset_class=views.SpeciesFilter), name="species-search"),
    path(r"species/<int:pk>", views.SpeciesDetail.as_view(), name="species-detail"),
    path(r"thermo/<int:pk>", views.ThermoDetail.as_view(), name="thermo-detail"),
    path(r"transport/<int:pk>", views.TransportDetail.as_view(), name="transport-detail"),
    path(r"source/<int:pk>", views.SourceDetail.as_view(), name="source-detail"),
    path(r"source_search/", FilterView.as_view(filterset_class=views.SourceFilter), name="source-search")
]
