from django.contrib import admin
from django.contrib.admin.options import TabularInline
from django.db.models import Model
from django.urls.conf import path
from database import models, views

for name in dir(models):
    obj = getattr(models, name)
    if (
        not name.startswith("_")
        and name
        not in [
            "Stoichiometry",
            "Reaction",
            "Source",
            "KineticModel",
            "PDepArrhenius",
            "BaseKineticsData",
            "ThermoComment",
            "TransportComment",
            "Authorship",
            "Pressure",
            "Efficiency",
            "RevisionMixin",
            "User",
            "SpeciesRevision",
            "ReactionRevision",
            "RevisionManagerMixin",
            "KineticModelRevision",
            "SpeciesName",
        ]
        and isinstance(obj, type)
        and issubclass(obj, Model)
    ):
        admin.site.register(obj)


class RevisionAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in obj._meta.fields]

    def get_urls(self):
        urls = super().get_urls()

        return [
            path(
                f"{self.url_name}/<int:pk>",
                self.admin_site.admin_view(self.approval_view.as_view()),
                name=self.url_name,
            ),
            *urls,
        ]

    def render_change_form(self, request, context, *args, **kwargs):
        context["url_name"] = f"admin:{self.url_name}"

        return super().render_change_form(request, context, *args, **kwargs)


class ImmutablePermissionMixin:
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class IsomerInline(ImmutablePermissionMixin, TabularInline):
    model = models.Species.isomers.through
    readonly_fields = ("isomer",)


@admin.register(models.SpeciesRevision)
class SpeciesRevisionAdmin(admin.ModelAdmin):
    exclude = ("hash", "isomers")
    inlines = [IsomerInline]
    url_name = "species-approval"
    approval_view = views.SpeciesRevisionApprovalView


class StoichiometryInline(admin.TabularInline):
    model = models.Stoichiometry
    fields = ("species", "coeff")


class StoichiometryRevisionInline(ImmutablePermissionMixin, admin.TabularInline):
    model = models.StoichiometryRevision
    fields = ("species", "coeff")


@admin.register(models.Reaction)
class ReactionAdmin(admin.ModelAdmin):
    inlines = [StoichiometryInline]


@admin.register(models.ReactionRevision)
class ReactionRevisionAdmin(RevisionAdmin):
    inlines = [StoichiometryRevisionInline]
    url_name = "reaction-approval"
    approval_view = views.ReactionRevisionApprovalView


class AuthorshipInline(admin.TabularInline):
    model = models.Authorship
    fields = ("author", "order")


@admin.register(models.Source)
class SourceAdmin(admin.ModelAdmin):
    inlines = [AuthorshipInline]


class PressureInline(admin.TabularInline):
    model = models.Pressure
    fields = ("arrhenius", "pressure")


@admin.register(models.PDepArrhenius)
class PDepArrheniusAdmin(admin.ModelAdmin):
    inlines = [PressureInline]


class EfficiencyInline(admin.TabularInline):
    model = models.Efficiency
    fields = ("species", "efficiency")


@admin.register(models.BaseKineticsData)
class BaseKineticsDataAdmin(admin.ModelAdmin):
    inlines = [EfficiencyInline]


class SpeciesNameInline(admin.TabularInline):
    model = models.SpeciesName
    fields = ("species", "name")


class ThermoCommentInline(admin.TabularInline):
    model = models.ThermoComment
    fields = ("thermo", "comment")


class TransportCommentInline(admin.TabularInline):
    model = models.TransportComment
    fields = ("transport", "comment")


class KineticsCommentInline(admin.TabularInline):
    model = models.KineticsComment
    fields = ("kinetics", "comment")


@admin.register(models.KineticModel)
class KineticModelAdmin(admin.ModelAdmin):
    inlines = [
        SpeciesNameInline,
        ThermoCommentInline,
        TransportCommentInline,
        KineticsCommentInline,
    ]


class SpeciesNameRevisionInline(ImmutablePermissionMixin, SpeciesNameInline):
    model = models.SpeciesNameRevision


class KineticsCommentRevisionInline(ImmutablePermissionMixin, KineticsCommentInline):
    model = models.KineticsCommentRevision


class ThermoCommentRevisionInline(ImmutablePermissionMixin, ThermoCommentInline):
    model = models.ThermoCommentRevision


class TransportCommentRevisionInline(ImmutablePermissionMixin, TransportCommentInline):
    model = models.TransportCommentRevision


@admin.register(models.KineticModelRevision)
class KineticModelRevisionAdmin(admin.ModelAdmin):
    inlines = [
        SpeciesNameRevisionInline,
        ThermoCommentRevisionInline,
        TransportCommentRevisionInline,
        KineticsCommentRevisionInline,
    ]
    url_name = "kinetic-model-revision"
    approval_view = views.KineticModelRevisionApprovalView
