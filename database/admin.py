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
            "SpeciesName",
            "KineticsComment",
            "ThermoComment",
            "TransportComment",
            "Authorship",
            "Pressure",
            "Efficiency",
            "RevisionMixin",
            "User",
            "RevisionManagerMixin",
            "MasterMixin",
            "ProposalManagerMixin",
            "SpeciesProposal",
            "ReactionProposal",
            "KineticModelProposal"
        ]
        and isinstance(obj, type)
        and issubclass(obj, Model)
    ):
        admin.site.register(obj)


class ProposalAdmin(admin.ModelAdmin):
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


class IsomerRevisionInline(ImmutablePermissionMixin, TabularInline):
    model = models.Species.isomers.through
    readonly_fields = ("isomer",)


@admin.register(models.SpeciesProposal)
class SpeciesProposalAdmin(admin.ModelAdmin):
    exclude = ("hash", "isomers")
    inlines = [IsomerRevisionInline]
    url_name = "species-approval"
    approval_view = views.SpeciesRevisionApprovalView


class StoichiometryInline(admin.TabularInline):
    model = models.Stoichiometry
    fields = ("species", "coeff")


class StoichiometryRevisionInline(ImmutablePermissionMixin, StoichiometryInline):
    pass


@admin.register(models.Reaction)
class ReactionAdmin(admin.ModelAdmin):
    inlines = [StoichiometryInline]


@admin.register(models.ReactionProposal)
class ReactionProposalAdmin(ProposalAdmin):
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
    pass


class KineticsCommentRevisionInline(ImmutablePermissionMixin, KineticsCommentInline):
    pass


class ThermoCommentRevisionInline(ImmutablePermissionMixin, ThermoCommentInline):
    pass


class TransportCommentRevisionInline(ImmutablePermissionMixin, TransportCommentInline):
    pass


@admin.register(models.KineticModelProposal)
class KineticModelProposalAdmin(ProposalAdmin):
    inlines = [
        SpeciesNameRevisionInline,
        ThermoCommentRevisionInline,
        TransportCommentRevisionInline,
        KineticsCommentRevisionInline,
    ]
    url_name = "kinetic-model-revision"
    approval_view = views.KineticModelRevisionApprovalView
