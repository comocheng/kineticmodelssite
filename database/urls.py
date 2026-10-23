from django.urls import path
from database import views

urlpatterns = [
    path(r"", views.BaseView.as_view(), name="home"),
    path(r"register/", views.RegistrationView.as_view(), name="register"),
    path(
        r"isomer-autocomplete/",
        views.IsomerAutocompleteView.as_view(),
        name="isomer-autocomplete",
    ),
    path(
        r"structure-autocomplete/",
        views.StructureAutocompleteView.as_view(),
        name="structure-autocomplete",
    ),
    path(
        r"species-autocomplete/",
        views.SpeciesAutocompleteView.as_view(),
        name="species-autocomplete",
    ),
    path(
        r"species_search/",
        views.SpeciesFilterView.as_view(),
        name="species-search",
    ),
    path(r"species/<int:pk>", views.SpeciesDetail.as_view(), name="species-detail"),
    path(r"thermo/<int:pk>", views.ThermoDetail.as_view(), name="thermo-detail"),
    path(r"transport/<int:pk>", views.TransportDetail.as_view(), name="transport-detail"),
    
    # Source URLs
    path(r"source/<int:pk>", views.SourceDetail.as_view(), name="source-detail"),
    path(r"source_search/", views.SourceFilterView.as_view(), name="source-search"),
    path(r"source/create/", views.SourceCreateView.as_view(), name="source-create"),
    path(r"source/<int:pk>/edit/", views.SourceUpdateView.as_view(), name="source-update"),
    path(r"source/<int:pk>/delete/", views.SourceDeleteView.as_view(), name="source-delete"),
    
    # Reaction URLs
    path(r"reaction_search/", views.ReactionFilterView.as_view(), name="reaction-search"),
    path(r"reaction/<int:pk>", views.ReactionDetail.as_view(), name="reaction-detail"),
    path(r"kinetics/<int:pk>", views.KineticsDetail.as_view(), name="kinetics-detail"),
    
    # KineticModel URLs
    path(r"kineticmodel/<int:pk>", views.KineticModelDetail.as_view(), name="kinetic-model-detail"),
    path(
        r"kineticmodel/<int:pk>/download/<str:format>",
        views.KineticModelDownloadView.as_view(),
        name="kinetic-model-download",
    ),
    path(r"kineticmodel_search/", views.KineticModelFilterView.as_view(), name="kinetic-model-list"),
    path(r"kineticmodel/compare/", views.KineticModelCompare.as_view(), name="kinetic-model-compare"),
    path(r"kineticmodel/similarity/", views.KineticModelSimilarity.as_view(), name="kinetic-model-similarity"),
    path(r"submechanism/", views.SubMechanismList.as_view(), name="sub-mechanism-list"),
    path(r"submechanism/<int:pk>", views.SubMechanismDetail.as_view(), name="sub-mechanism-detail"),
    path(r"chemistry-block/<int:pk>", views.ChemistryBlockDetail.as_view(), name="chemistry-block-detail"),
    path(r"rmg/libraries/", views.RMGLibraryList.as_view(), name="rmg-library-list"),
    path(r"rmg/library/<str:kind>/<path:name>", views.RMGLibraryDetail.as_view(), name="rmg-library-detail"),
    path(r"rmg/families/", views.RMGFamilyList.as_view(), name="rmg-family-list"),
    path(r"rmg/family/<str:name>", views.RMGFamilyDetail.as_view(), name="rmg-family-detail"),
    path(r"kineticmodel/create/", views.KineticModelCreateView.as_view(), name="kinetic-model-create"),
    path(r"kineticmodel/<int:pk>/edit/", views.KineticModelUpdateView.as_view(), name="kinetic-model-update"),
    path(r"kineticmodel/<int:pk>/delete/", views.KineticModelDeleteView.as_view(), name="kinetic-model-delete"),
    
    # Author URLs
    path(r"authors/", views.AuthorListView.as_view(), name="author-list"),
    path(r"author/create/", views.AuthorCreateView.as_view(), name="author-create"),
    path(r"author/<int:pk>/edit/", views.AuthorUpdateView.as_view(), name="author-update"),
    path(r"author/<int:pk>/delete/", views.AuthorDeleteView.as_view(), name="author-delete"),
    
    # Utility URLs
    path(r"drawstructure/<int:pk>", views.DrawStructure.as_view(), name="draw-structure"),
]
