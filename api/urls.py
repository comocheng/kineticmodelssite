from django.urls import path
from rest_framework import routers

from api import views, chemked_views, analysis_views, metadata_views, provenance_views
from api.contribution_views import ContributeFilesView, ContributionStatusView


router = routers.DefaultRouter()
router.register(r"formula", views.FormulaViewSet, basename="api-formula")
router.register(r"isomer", views.IsomerViewSet, basename="api-isomer")
router.register(r"species", views.SpeciesViewSet, basename="api-species")
router.register(r"reaction", views.ReactionViewSet, basename="api-reaction")
router.register(r"thermo", views.ThermoViewSet, basename="api-thermo")
router.register(r"thermo-record", views.ThermoRecordViewSet, basename="api-thermo-record")
router.register(r"thermo-enrichment", views.ThermoEnrichmentJobViewSet, basename="api-thermo-enrichment")
router.register(r"transport", views.TransportViewSet, basename="api-transport")
router.register(r"kinetics", views.KineticsViewSet, basename="api-kinetics")
router.register(r"kineticmodel", views.KineticModelViewSet, basename="api-kineticmodel")

# database: bibliography and structure (admin-writable, public read)
router.register(r"source", views.SourceViewSet, basename="api-source")
router.register(r"author", views.AuthorViewSet, basename="api-author")
router.register(r"structure", views.StructureViewSet, basename="api-structure")

# chemked_database: experimental data (read-only)
router.register(r"experiment-dataset", chemked_views.ExperimentDatasetViewSet, basename="api-experiment-dataset")
router.register(r"experiment-datapoint", chemked_views.ExperimentDatapointViewSet, basename="api-experiment-datapoint")
router.register(r"apparatus", chemked_views.ApparatusViewSet, basename="api-apparatus")
router.register(r"common-properties", chemked_views.CommonPropertiesViewSet, basename="api-common-properties")
router.register(r"composition", chemked_views.CompositionViewSet, basename="api-composition")
router.register(r"composition-species", chemked_views.CompositionSpeciesViewSet, basename="api-composition-species")
router.register(r"ignition-delay", chemked_views.IgnitionDelayViewSet, basename="api-ignition-delay")
router.register(r"laminar-burning-velocity", chemked_views.LaminarBurningVelocityViewSet, basename="api-laminar-burning-velocity")
router.register(r"rate-coefficient", chemked_views.RateCoefficientViewSet, basename="api-rate-coefficient")
router.register(r"concentration-time-profile", chemked_views.ConcentrationTimeProfileViewSet, basename="api-concentration-time-profile")
router.register(r"jet-stirred-reactor", chemked_views.JetStirredReactorViewSet, basename="api-jet-stirred-reactor")
router.register(r"outlet-concentration", chemked_views.OutletConcentrationViewSet, basename="api-outlet-concentration")
router.register(r"burner-stabilized-flame", chemked_views.BurnerStabilizedFlameViewSet, basename="api-burner-stabilized-flame")

# analysis: simulation results and agreement metrics (read-only)
router.register(r"simulation-run", analysis_views.SimulationRunViewSet, basename="api-simulation-run")
router.register(r"simulation-result", analysis_views.SimulationResultViewSet, basename="api-simulation-result")
router.register(r"datapoint-result", analysis_views.DatapointResultViewSet, basename="api-datapoint-result")
router.register(r"species-mapping", analysis_views.SpeciesMappingViewSet, basename="api-species-mapping")
router.register(r"model-dataset-coverage", analysis_views.ModelDatasetCoverageViewSet, basename="api-model-dataset-coverage")
router.register(r"fuel-group", analysis_views.FuelGroupViewSet, basename="api-fuel-group")
router.register(r"fuel-species", analysis_views.FuelSpeciesViewSet, basename="api-fuel-species")
router.register(r"fuel-model-compatibility", analysis_views.FuelModelCompatibilityViewSet, basename="api-fuel-model-compatibility")

# provenance: FAIR identity, licensing, and semantic mappings (read-only)
router.register(r"institution", provenance_views.InstitutionViewSet, basename="api-institution")
router.register(r"person", provenance_views.PersonViewSet, basename="api-person")
router.register(r"license", provenance_views.LicenseViewSet, basename="api-license")
router.register(r"external-identifier", provenance_views.ExternalIdentifierViewSet, basename="api-external-identifier")
router.register(r"semantic-mapping", provenance_views.SemanticMappingViewSet, basename="api-semantic-mapping")

urlpatterns = router.urls + [
    path("contribute/", ContributeFilesView.as_view(), name="api-contribute"),
    path("contribute/status/<int:pr_number>/", ContributionStatusView.as_view(), name="api-contribute-status"),
    # FAIR JSON-LD metadata endpoints
    path("metadata/", metadata_views.catalog_metadata, name="api-fair-metadata"),
    path("source/<int:pk>/metadata/", metadata_views.source_metadata, name="api-source-metadata"),
    path("kineticmodel/<int:pk>/metadata/", metadata_views.kinetic_model_metadata, name="api-kineticmodel-metadata"),
    path("experiment-dataset/<int:pk>/metadata/", metadata_views.experiment_dataset_metadata, name="api-experiment-dataset-metadata"),
]
