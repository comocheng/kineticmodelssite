from django.urls import path
from database import views

urlpatterns = [
    path(r"", views.BaseView.as_view(), name="home"),
    path(r"register/", views.RegistrationView.as_view(), name="register"),
    path(
        r"species_search/",
        views.SpeciesFilterView.as_view(),
        name="species-search",
    ),
    path(r"species/<int:pk>", views.SpeciesDetail.as_view(), name="species-detail"),
    path(
        r"species/<int:pk>/revise",
        views.SpeciesRevisionView.as_view(),
        name="species-revision",
    ),
    path(r"thermo/<int:pk>", views.ThermoDetail.as_view(), name="thermo-detail"),
    path(r"transport/<int:pk>", views.TransportDetail.as_view(), name="transport-detail"),
    path(r"source/<int:pk>", views.SourceDetail.as_view(), name="source-detail"),
    path(
        r"source_search/",
        views.SourceFilterView.as_view(),
        name="source-search",
    ),
    path(
        r"reaction_search/",
        views.ReactionFilterView.as_view(),
        name="reaction-search",
    ),
    path(r"reaction/<int:pk>", views.ReactionDetail.as_view(), name="reaction-detail"),
    path(
        r"reaction/<int:pk>/revise",
        views.ReactionRevisionView.as_view(),
        name="reaction-revision",
    ),
    path(r"kinetics/<int:pk>", views.KineticsDetail.as_view(), name="kinetics-detail"),
    path(r"kineticmodel/<int:pk>", views.KineticModelDetail.as_view(), name="kinetic-model-detail"),
    path(r"drawstructure/<int:pk>", views.DrawStructure.as_view(), name="draw-structure"),
]
