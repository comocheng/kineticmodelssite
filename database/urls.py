from django.urls import path
from django_filters.views import FilterView

from . import views

urlpatterns = [
    path(r"species_search/", FilterView.as_view(filterset_class=views.SpeciesFilter), name="species-search"),
]
