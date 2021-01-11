from django.urls import path, include
from rest_framework import routers

from api import views


router = routers.DefaultRouter()
router.register(r"formula", views.FormulaViewSet)
router.register(r"isomer", views.IsomerViewSet)
router.register(r"species", views.SpeciesViewSet)
router.register(r"reaction", views.ReactionViewSet)
router.register(r"thermo", views.ThermoViewSet)
router.register(r"transport", views.TransportViewSet)
router.register(r"kinetics", views.KineticsViewSet)
router.register(r"kineticmodel", views.KineticModelViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
