from django.contrib import admin

from provenance import models


@admin.register(models.Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name", "ror_id", "country", "parent")
    search_fields = ("name", "ror_id")
    list_filter = ("country",)


@admin.register(models.Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "orcid", "affiliation")
    search_fields = ("family_name", "given_name", "full_name", "orcid")
    list_filter = ("affiliation",)


@admin.register(models.License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ("spdx_id", "name", "url")
    search_fields = ("spdx_id", "name")


@admin.register(models.ExternalIdentifier)
class ExternalIdentifierAdmin(admin.ModelAdmin):
    list_display = ("scheme", "value", "content_type", "object_id", "is_primary")
    list_filter = ("scheme", "is_primary")
    search_fields = ("value",)


@admin.register(models.SemanticMapping)
class SemanticMappingAdmin(admin.ModelAdmin):
    list_display = ("subject_id", "predicate_id", "object_id", "confidence", "mapping_tool")
    list_filter = ("predicate_id", "mapping_tool")
    search_fields = ("subject_id", "subject_label", "object_id", "object_label")
