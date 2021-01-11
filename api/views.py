from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission, SAFE_METHODS
from rest_framework.decorators import action
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from database import models
from api import serializers
from api.models import Revision


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class PermissionsMixin:
    permission_classes = [IsAdminUser | (IsAuthenticated & ReadOnly)]


class RevisionMixin:
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="rev",
    )
    def proposal_create(self, request):
        proposal_comment = request.data.pop("proposal_comment", "")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Revision.objects.create(
            content_type=ContentType.objects.get_for_model(self.get_serializer_class().Meta.model),
            created_by=self.request.user,
            proposal_comment=proposal_comment,
            diff=request.data,
        )

        return Response(status=status.HTTP_200_OK)

    @action(
        detail=True, methods=["get", "patch"], permission_classes=[IsAuthenticated], url_path="rev"
    )
    def proposal_list_update(self, request, pk=None):
        if request.method == "GET":
            model = self.get_serializer_class().Meta.model
            content_type = ContentType.objects.get_for_model(model)
            queryset = Revision.objects.filter(
                content_type=content_type,
                diff__id=int(pk),
                status=Revision.PENDING,
            )
            serializer = serializers.RevisionSerializer(
                queryset,
                many=True,
            )

            return Response(serializer.data)
        if request.method == "PATCH":
            proposal_comment = request.data.pop("proposal_comment", "")
            serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            Revision.objects.create(
                content_type=ContentType.objects.get_for_model(
                    self.get_serializer_class().Meta.model
                ),
                created_by=self.request.user,
                proposal_comment=proposal_comment,
                diff=request.data,
            )

            return Response(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
        url_path="rev/(?P<rev_pk>[^/.]+)/approve",
    )
    def approve(self, request, rev_pk=None, pk=None):
        reviewer_comment = request.data.get("reviewer_comment", "")
        try:
            revision = Revision.objects.get(pk=rev_pk)
            revision.reviewed_by = self.request.user
            revision.reviewer_comment = reviewer_comment
            revision.status = revision.APPROVED
            revision.save()
            pk = revision.diff.get("id")
            request = HttpRequest()
            request.data = revision.diff
            if pk:
                return self.partial_update(request, pk=pk)
            else:
                return self.create(request)
        except Revision.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
        url_path="rev/(?P<rev_pk>[^/.]+)/deny",
    )
    def deny(self, request, rev_pk, pk=None):
        reviewer_comment = request.data.get("reviewer_comment", "")
        try:
            revision = Revision.objects.get(pk=rev_pk)
            revision.reviewed_by = self.request.user
            revision.reviewer_comment = reviewer_comment
            revision.status = revision.DENIED
            revision.save()
            return Response(status=status.HTTP_200_OK)
        except Revision.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class DatabaseViewSet(PermissionsMixin, RevisionMixin, viewsets.ModelViewSet):
    pass


class FormulaViewSet(DatabaseViewSet):
    queryset = models.Formula.objects.all()
    serializer_class = serializers.FormulaSerializer


class IsomerViewSet(DatabaseViewSet):
    queryset = models.Isomer.objects.all()
    serializer_class = serializers.IsomerSerializer


class SpeciesViewSet(DatabaseViewSet):
    queryset = models.Species.objects.all()
    serializer_class = serializers.SpeciesSerializer


class ReactionViewSet(DatabaseViewSet):
    queryset = models.Reaction.objects.all()
    serializer_class = serializers.ReactionSerializer


class ThermoViewSet(DatabaseViewSet):
    queryset = models.Thermo.objects.all()
    serializer_class = serializers.ThermoSerializer


class TransportViewSet(DatabaseViewSet):
    queryset = models.Transport.objects.all()
    serializer_class = serializers.TransportSerializer


class KineticsViewSet(DatabaseViewSet):
    queryset = models.Kinetics.objects.all()
    serializer_class = serializers.KineticsSerializer


class KineticModelViewSet(DatabaseViewSet):
    queryset = models.KineticModel.objects.all()
    serializer_class = serializers.KineticModelSerializer
