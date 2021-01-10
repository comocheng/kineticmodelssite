from rest_framework import routers

from api import views


router = routers.DefaultRouter()
router.register(r"formula", views.FormulaViewSet, basename="api-formula")
router.register(r"isomer", views.IsomerViewSet, basename="api-isomer")
router.register(r"species", views.SpeciesViewSet, basename="api-species")
router.register(r"reaction", views.ReactionViewSet, basename="api-reaction")
router.register(r"thermo", views.ThermoViewSet, basename="api-thermo")
router.register(r"transport", views.TransportViewSet, basename="api-transport")
router.register(r"kinetics", views.KineticsViewSet, basename="api-kinetics")
router.register(r"kineticmodel", views.KineticModelViewSet, basename="api-kineticmodel")

urlpatterns = router.urls
