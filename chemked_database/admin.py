from django.contrib import admin

from .models import (
	Apparatus,
	BurnerStabilizedFlameSpeciationMeasurementDatapoint,
	CommonProperties,
	Composition,
	CompositionSpecies,
	ConcentrationTimeProfileMeasurementDatapoint,
	EvaluatedStandardDeviation,
	ExperimentDataset,
	ExperimentDatapoint,
	FileAuthor,
	IgnitionDelayDatapoint,
	JetStirredReactorMeasurementDatapoint,
	LaminarBurningVelocityMeasurementDatapoint,
	OutletConcentrationMeasurementDatapoint,
	ReferenceAuthor,
	RCMData,
	SpeciesThermo,
	TimeHistory,
	ValueWithUnit,
	VolumeHistory,
)


class CompositionSpeciesInline(admin.TabularInline):
	model = CompositionSpecies
	extra = 0


@admin.register(ExperimentDataset)
class ExperimentDatasetAdmin(admin.ModelAdmin):
	list_display = ("chemked_file_path", "experiment_type", "reference_year", "is_valid")
	search_fields = ("chemked_file_path", "reference_doi", "reference_journal")
	list_filter = ("experiment_type", "is_valid")


@admin.register(ExperimentDatapoint)
class ExperimentDatapointAdmin(admin.ModelAdmin):
	list_display = ("dataset", "temperature", "pressure")
	search_fields = ("dataset__chemked_file_path",)


@admin.register(CommonProperties)
class CommonPropertiesAdmin(admin.ModelAdmin):
	list_display = ("dataset", "ignition_target", "ignition_type")


@admin.register(Composition)
class CompositionAdmin(admin.ModelAdmin):
	list_display = ("id", "kind")
	inlines = (CompositionSpeciesInline,)


@admin.register(CompositionSpecies)
class CompositionSpeciesAdmin(admin.ModelAdmin):
	list_display = ("composition", "species_name", "amount")
	search_fields = ("species_name", "inchi", "smiles")


@admin.register(SpeciesThermo)
class SpeciesThermoAdmin(admin.ModelAdmin):
	list_display = ("species", "t_range_1", "t_range_2", "t_range_3")


@admin.register(IgnitionDelayDatapoint)
class IgnitionDelayDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "ignition_delay", "ignition_target", "ignition_type")


@admin.register(LaminarBurningVelocityMeasurementDatapoint)
class LaminarBurningVelocityMeasurementDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "laminar_burning_velocity", "stretch")


@admin.register(ConcentrationTimeProfileMeasurementDatapoint)
class ConcentrationTimeProfileMeasurementDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "tracked_species")


@admin.register(JetStirredReactorMeasurementDatapoint)
class JetStirredReactorMeasurementDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint",)


@admin.register(OutletConcentrationMeasurementDatapoint)
class OutletConcentrationMeasurementDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint",)


@admin.register(BurnerStabilizedFlameSpeciationMeasurementDatapoint)
class BurnerStabilizedFlameSpeciationMeasurementDatapointAdmin(admin.ModelAdmin):
	list_display = ("datapoint",)


@admin.register(EvaluatedStandardDeviation)
class EvaluatedStandardDeviationAdmin(admin.ModelAdmin):
	list_display = ("dataset", "reference", "kind", "method", "value", "units")


@admin.register(RCMData)
class RCMDataAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "compressed_temperature", "compressed_pressure")


@admin.register(TimeHistory)
class TimeHistoryAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "history_type", "num_points")


@admin.register(VolumeHistory)
class VolumeHistoryAdmin(admin.ModelAdmin):
	list_display = ("datapoint", "time_units", "volume_units")


@admin.register(Apparatus)
class ApparatusAdmin(admin.ModelAdmin):
	list_display = ("kind", "institution", "facility")


@admin.register(FileAuthor)
class FileAuthorAdmin(admin.ModelAdmin):
	list_display = ("name", "orcid")
	search_fields = ("name", "orcid")


@admin.register(ReferenceAuthor)
class ReferenceAuthorAdmin(admin.ModelAdmin):
	list_display = ("name", "orcid")
	search_fields = ("name", "orcid")


@admin.register(ValueWithUnit)
class ValueWithUnitAdmin(admin.ModelAdmin):
	list_display = ("value", "units", "uncertainty_type")
