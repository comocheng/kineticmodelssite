from database.models.source import Author
from database.models.reaction_species import Stoichiometry
from django.contrib import admin
from django.db.models import Model
from database import models

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
        ]
        and isinstance(obj, type)
        and issubclass(obj, Model)
    ):
        admin.site.register(obj)


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
