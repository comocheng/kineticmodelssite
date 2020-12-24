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
            "Species",
            "SpeciesRevision",
        ]
        and isinstance(obj, type)
        and issubclass(obj, Model)
    ):
        admin.site.register(obj)


class RevisionAdmin(admin.ModelAdmin):

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in obj._meta.fields]


class IsomerInline(TabularInline):
    model = models.Species.isomers.through
    readonly_fields = ("isomer",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(models.Species)
class SpeciesRevisionAdmin(RevisionAdmin):
    exclude = ("hash", "isomers")
    inlines = [IsomerInline]

    def get_urls(self):
        urls = super().get_urls()

        return [
            path(
                r"species/<int:pk>/approve",
                self.admin_site.admin_view(views.RevisionApprovalView.as_view()),
                name="species-approval",
            ),
            *urls,
        ]


class StoichiometryInline(admin.TabularInline):
    model = models.Stoichiometry
    fields = ("species", "stoichiometry")


@admin.register(models.Reaction)
class ReactionAdmin(admin.ModelAdmin):
    inlines = [StoichiometryInline]


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
