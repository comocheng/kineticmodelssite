from django.conf.urls import url
from django_filters.views import FilterView

from . import views

urlpatterns = [
    url(r"species_search/", FilterView.as_view(filterset_class=views.SpeciesFilter)),
]
