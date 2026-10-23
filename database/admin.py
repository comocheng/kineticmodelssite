"""
Django admin configuration for the kinetic models database.
Provides administrative interface for managing all database models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    # Core models
    KineticModel,
    Species,
    Reaction,
    Kinetics,
    Source,
    Thermo,
    Transport,
    # Supporting models
    Formula,
    Isomer,
    Structure,
    Stoichiometry,
    Author,
    Authorship,
    SpeciesName,
    KineticsComment,
    ThermoComment,
    TransportComment,
)
from .models.kinetic_data import Efficiency
from .models import ThermoRecord, ThermoEnrichmentJob, ThermoProviderStatus, SubMechanism


@admin.register(ThermoEnrichmentJob)
class ThermoEnrichmentJobAdmin(admin.ModelAdmin):
    list_display = ("structure_id", "provider", "status", "attempts", "next_attempt_at", "updated_at")
    list_filter = ("provider", "status")
    search_fields = ("structure__smiles", "message")
    readonly_fields = tuple(field.name for field in ThermoEnrichmentJob._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(ThermoProviderStatus)
class ThermoProviderStatusAdmin(admin.ModelAdmin):
    list_display = ("provider", "retry_after", "message")
    readonly_fields = tuple(field.name for field in ThermoProviderStatus._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(ThermoRecord)
class ThermoRecordAdmin(admin.ModelAdmin):
    list_display = ("label", "provider", "external_id", "source_version", "species", "retrieved_at")
    list_filter = ("provider", "phase")
    search_fields = ("label", "external_id")
    readonly_fields = tuple(field.name for field in ThermoRecord._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# Inline Admin Classes
# =============================================================================

class AuthorshipInline(admin.TabularInline):
    """Inline for managing authors of a source."""
    model = Authorship
    extra = 1
    autocomplete_fields = ['author']


class SpeciesNameInline(admin.TabularInline):
    """Inline for managing species names in a kinetic model."""
    model = SpeciesName
    extra = 1
    autocomplete_fields = ['species']


class KineticsCommentInline(admin.TabularInline):
    """Inline for managing kinetics comments in a kinetic model."""
    model = KineticsComment
    extra = 0
    autocomplete_fields = ['kinetics']


class ThermoCommentInline(admin.TabularInline):
    """Inline for managing thermo comments in a kinetic model."""
    model = ThermoComment
    extra = 0
    autocomplete_fields = ['thermo']


class TransportCommentInline(admin.TabularInline):
    """Inline for managing transport comments in a kinetic model."""
    model = TransportComment
    extra = 0
    autocomplete_fields = ['transport']


class StoichiometryInline(admin.TabularInline):
    """Inline for managing stoichiometry in a reaction."""
    model = Stoichiometry
    extra = 2
    autocomplete_fields = ['species']


class EfficiencyInline(admin.TabularInline):
    """Inline for managing third-body efficiencies in kinetics."""
    model = Efficiency
    extra = 0
    autocomplete_fields = ['species']


class StructureInline(admin.TabularInline):
    """Inline for viewing structures of an isomer."""
    model = Structure
    extra = 0
    fields = ['smiles', 'multiplicity', 'adjacency_list']


# =============================================================================
# Admin Classes
# =============================================================================

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('lastname', 'firstname', 'name')
    search_fields = ('lastname', 'firstname')
    ordering = ('lastname', 'firstname')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_title_short', 'publication_year', 'journal_name', 'doi_link')
    list_filter = ('publication_year', 'journal_name')
    search_fields = ('source_title', 'doi', 'prime_id', 'authors__lastname')
    ordering = ('-publication_year', 'source_title')
    inlines = [AuthorshipInline]
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('doi', 'prime_id')
        }),
        ('Publication Details', {
            'fields': ('source_title', 'publication_year', 'journal_name', 
                      'journal_volume_number', 'page_numbers')
        }),
    )
    
    def source_title_short(self, obj):
        """Truncate long titles for display."""
        if obj.source_title and len(obj.source_title) > 60:
            return obj.source_title[:60] + '...'
        return obj.source_title or '-'
    source_title_short.short_description = 'Title'
    
    def doi_link(self, obj):
        """Create clickable DOI link."""
        if obj.doi:
            return format_html('<a href="https://doi.org/{}" target="_blank">{}</a>', obj.doi, obj.doi)
        return '-'
    doi_link.short_description = 'DOI'


@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display = ('formula',)
    search_fields = ('formula',)
    ordering = ('formula',)


@admin.register(Isomer)
class IsomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'inchi_short', 'formula')
    list_filter = ('formula',)
    search_fields = ('inchi', 'formula__formula')
    autocomplete_fields = ['formula']
    inlines = [StructureInline]
    
    def inchi_short(self, obj):
        """Truncate long InChI strings."""
        if len(obj.inchi) > 50:
            return obj.inchi[:50] + '...'
        return obj.inchi
    inchi_short.short_description = 'InChI'


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ('id', 'smiles', 'multiplicity', 'isomer')
    list_filter = ('multiplicity',)
    search_fields = ('smiles', 'adjacency_list', 'isomer__inchi')
    autocomplete_fields = ['isomer']


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ('id', 'formula', 'prime_id', 'cas_number', 'isomer_count')
    list_filter = ('isomers__formula',)
    search_fields = ('hash', 'prime_id', 'cas_number', 'speciesname__name')
    filter_horizontal = ('isomers',)
    
    def isomer_count(self, obj):
        return obj.isomers.count()
    isomer_count.short_description = '# Isomers'


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'equation', 'reversible', 'prime_id', 'species_count')
    list_filter = ('reversible',)
    search_fields = ('hash', 'prime_id')
    inlines = [StoichiometryInline]
    
    def species_count(self, obj):
        return obj.species.count()
    species_count.short_description = '# Species'


@admin.register(Stoichiometry)
class StoichiometryAdmin(admin.ModelAdmin):
    list_display = ('id', 'reaction', 'species', 'coeff')
    list_filter = ('coeff',)
    search_fields = ('reaction__prime_id', 'species__prime_id')
    autocomplete_fields = ['species', 'reaction']


@admin.register(Kinetics)
class KineticsAdmin(admin.ModelAdmin):
    list_display = ('id', 'reaction', 'source', 'type', 'temp_range', 'pressure_range')
    list_filter = ('reverse',)
    search_fields = ('prime_id', 'reaction__prime_id', 'source__source_title')
    autocomplete_fields = ['reaction', 'source']
    inlines = [EfficiencyInline]
    readonly_fields = ('type',)
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('prime_id', 'reaction', 'source', 'reverse')
        }),
        ('Conditions', {
            'fields': (('min_temp', 'max_temp'), ('min_pressure', 'max_pressure'))
        }),
        ('Kinetic Data', {
            'fields': ('raw_data', 'type', 'relative_uncertainty'),
            'classes': ('wide',)
        }),
    )
    
    def temp_range(self, obj):
        if obj.min_temp and obj.max_temp:
            return f"{obj.min_temp:.0f} - {obj.max_temp:.0f} K"
        return '-'
    temp_range.short_description = 'T Range'
    
    def pressure_range(self, obj):
        if obj.min_pressure and obj.max_pressure:
            return f"{obj.min_pressure:.0e} - {obj.max_pressure:.0e} Pa"
        return '-'
    pressure_range.short_description = 'P Range'


@admin.register(Thermo)
class ThermoAdmin(admin.ModelAdmin):
    list_display = ('id', 'species', 'source', 'preferred_key', 'temp_range', 'h298_display')
    search_fields = ('prime_id', 'preferred_key', 'species__prime_id')
    autocomplete_fields = ['species', 'source']
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('prime_id', 'preferred_key', 'species', 'source')
        }),
        ('Reference State', {
            'fields': ('reference_temp', 'reference_pressure', 'enthalpy_formation')
        }),
        ('Polynomial 1', {
            'fields': ('coeffs_poly1', ('temp_min_1', 'temp_max_1'))
        }),
        ('Polynomial 2', {
            'fields': ('coeffs_poly2', ('temp_min_2', 'temp_max_2'))
        }),
    )
    
    def temp_range(self, obj):
        return f"{obj.temp_min_1:.0f} - {obj.temp_max_2:.0f} K"
    temp_range.short_description = 'T Range'
    
    def h298_display(self, obj):
        try:
            return f"{obj.enthalpy298/1000:.2f} kJ/mol"
        except:
            return '-'
    h298_display.short_description = 'H298'


@admin.register(Transport)
class TransportAdmin(admin.ModelAdmin):
    list_display = ('id', 'species', 'source', 'geometry', 'collision_diameter', 'potential_well_depth')
    search_fields = ('prime_id', 'species__prime_id')
    autocomplete_fields = ['species', 'source']


@admin.register(KineticModel)
class KineticModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'model_name', 'prime_id', 'source', 'species_count', 'kinetics_count', 'has_files')
    list_filter = ('source__publication_year',)
    search_fields = ('model_name', 'prime_id', 'info', 'source__source_title')
    autocomplete_fields = ['source']
    inlines = [SpeciesNameInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('model_name', 'prime_id', 'source', 'info')
        }),
        ('CHEMKIN Files', {
            'fields': ('chemkin_reactions_file', 'chemkin_thermo_file', 'chemkin_transport_file'),
            'classes': ('collapse',)
        }),
    )
    
    def species_count(self, obj):
        return obj.species.count()
    species_count.short_description = '# Species'
    
    def kinetics_count(self, obj):
        return obj.kinetics.count()
    kinetics_count.short_description = '# Kinetics'
    
    def has_files(self, obj):
        has_rxn = bool(obj.chemkin_reactions_file)
        has_thermo = bool(obj.chemkin_thermo_file)
        has_trans = bool(obj.chemkin_transport_file)
        icons = []
        if has_rxn:
            icons.append('⚗️')
        if has_thermo:
            icons.append('🌡️')
        if has_trans:
            icons.append('🚗')
        return ' '.join(icons) if icons else '-'
    has_files.short_description = 'Files'


@admin.register(SpeciesName)
class SpeciesNameAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'kinetic_model')
    search_fields = ('name', 'species__prime_id', 'kinetic_model__model_name')
    autocomplete_fields = ['species', 'kinetic_model']


@admin.register(KineticsComment)
class KineticsCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'kinetics', 'kinetic_model', 'comment_short')
    search_fields = ('comment', 'kinetics__prime_id', 'kinetic_model__model_name')
    autocomplete_fields = ['kinetics', 'kinetic_model']
    
    def comment_short(self, obj):
        if obj.comment and len(obj.comment) > 50:
            return obj.comment[:50] + '...'
        return obj.comment or '-'
    comment_short.short_description = 'Comment'


@admin.register(ThermoComment)
class ThermoCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'thermo', 'kinetic_model', 'comment_short')
    search_fields = ('comment', 'thermo__prime_id', 'kinetic_model__model_name')
    autocomplete_fields = ['thermo', 'kinetic_model']
    
    def comment_short(self, obj):
        if obj.comment and len(obj.comment) > 50:
            return obj.comment[:50] + '...'
        return obj.comment or '-'
    comment_short.short_description = 'Comment'


@admin.register(TransportComment)
class TransportCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'transport', 'kinetic_model', 'comment_short')
    search_fields = ('comment', 'transport__prime_id', 'kinetic_model__model_name')
    autocomplete_fields = ['transport', 'kinetic_model']
    
    def comment_short(self, obj):
        if obj.comment and len(obj.comment) > 50:
            return obj.comment[:50] + '...'
        return obj.comment or '-'
    comment_short.short_description = 'Comment'


@admin.register(Authorship)
class AuthorshipAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'source', 'order')
    list_filter = ('order',)
    search_fields = ('author__lastname', 'source__source_title')
    autocomplete_fields = ['author', 'source']


@admin.register(Efficiency)
class EfficiencyAdmin(admin.ModelAdmin):
    list_display = ('id', 'species', 'kinetics', 'efficiency')
    search_fields = ('species__prime_id', 'kinetics__prime_id')
    autocomplete_fields = ['species', 'kinetics']


@admin.register(SubMechanism)
class SubMechanismAdmin(admin.ModelAdmin):
    """Rename sub-mechanisms (e.g. 'Aramco C1'); everything else comes from analyze_shared_chemistry."""
    list_display = ('id', 'default_name', 'name', 'layer', 'model_count', 'variant_count', 'reactions', 'core')
    list_editable = ('name',)
    list_filter = ('layer',)
    search_fields = ('name', 'default_name', 'origin__model_name')
    fields = ('name', 'default_name', 'layer', 'origin', 'model_count', 'variant_count', 'reactions', 'core', 'cohesion')
    readonly_fields = ('default_name', 'layer', 'origin', 'model_count', 'variant_count', 'reactions', 'core', 'cohesion')
