from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission, SAFE_METHODS

from database import models
from api import serializers


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class PermissionsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser | (IsAuthenticated & ReadOnly)]


class FormulaViewSet(PermissionsViewSet):
    queryset = models.Formula.objects.all()
    serializer_class = serializers.FormulaSerializer


class IsomerViewSet(PermissionsViewSet):
    queryset = models.Isomer.objects.all()
    serializer_class = serializers.IsomerSerializer


class SpeciesViewSet(PermissionsViewSet):
    queryset = models.Species.objects.all()
    serializer_class = serializers.SpeciesSerializer


class ReactionViewSet(PermissionsViewSet):
    queryset = models.Reaction.objects.all()
    serializer_class = serializers.ReactionSerializer


class ThermoViewSet(PermissionsViewSet):
    queryset = models.Thermo.objects.all()
    serializer_class = serializers.ThermoSerializer


class TransportViewSet(PermissionsViewSet):
    queryset = models.Transport.objects.all()
    serializer_class = serializers.TransportSerializer


class KineticsViewSet(PermissionsViewSet):
    queryset = models.Kinetics.objects.all()
    serializer_class = serializers.KineticsSerializer


class KineticModelViewSet(PermissionsViewSet):
    queryset = models.KineticModel.objects.all()
    serializer_class = serializers.KineticModelSerializer
