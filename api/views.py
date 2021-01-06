from rest_framework import viewsets

from database import models
from api import serializers


class FormulaViewSet(viewsets.ModelViewSet):
    queryset = models.Formula.objects.all()
    serializer_class = serializers.FormulaSerializer


class IsomerViewSet(viewsets.ModelViewSet):
    queryset = models.Isomer.objects.all()
    serializer_class = serializers.IsomerSerializer


class SpeciesViewSet(viewsets.ModelViewSet):
    queryset = models.Species.objects.all()
    serializer_class = serializers.SpeciesSerializer


class ReactionViewSet(viewsets.ModelViewSet):
    queryset = models.Reaction.objects.all()
    serializer_class = serializers.ReactionSerializer


class ThermoViewSet(viewsets.ModelViewSet):
    queryset = models.Thermo.objects.all()
    serializer_class = serializers.ThermoSerializer


class TransportViewSet(viewsets.ModelViewSet):
    queryset = models.Transport.objects.all()
    serializer_class = serializers.TransportSerializer


class KineticsViewSet(viewsets.ModelViewSet):
    queryset = models.Kinetics.objects.all()
    serializer_class = serializers.KineticsSerializer


class KineticModelViewSet(viewsets.ModelViewSet):
    queryset = models.KineticModel.objects.all()
    serializer_class = serializers.KineticModelSerializer
