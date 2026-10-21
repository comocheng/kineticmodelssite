"""
ChemKED Database Models

Models for storing experimental combustion data in ChemKED format.
Supports ignition delay experiments from shock tubes and rapid compression machines.

Reference: https://github.com/pr-omethe-us/ChemKED
Schema: https://github.com/pr-omethe-us/PyKED
"""

from django.db import models
from django.core.validators import MinValueValidator
import re


class ApparatusKind(models.TextChoices):
    """Types of experimental apparatus"""
    SHOCK_TUBE = 'shock tube', 'Shock Tube'
    RCM = 'rapid compression machine', 'Rapid Compression Machine'
    STIRRED_REACTOR = 'stirred reactor', 'Stirred Reactor'
    STIRRED_REACTOR_QUARTZ = 'stirred reactor (quartz)', 'Stirred Reactor (Quartz)'
    STIRRED_REACTOR_FUSED_SILICA = 'stirred reactor (fused silica)', 'Stirred Reactor (Fused Silica)'
    STIRRED_REACTION = 'stirred reaction', 'Stirred Reaction'
    JET_STIRRED_REACTOR = 'jet stirred reactor', 'Jet Stirred Reactor'
    FLOW_REACTOR = 'flow reactor', 'Flow Reactor'
    FLOW_REACTOR_QUARTZ = 'flow reactor (quartz)', 'Flow Reactor (Quartz)'
    FLOW_REACTOR_ALUMINA = 'flow reactor (alumina)', 'Flow Reactor (Alumina)'
    FLOW_REACTOR_RECRYSTALLIZED_ALUMINA = 'flow reactor (recrystallized alumina)', 'Flow Reactor (Recrystallized Alumina)'
    FLAME = 'flame', 'Flame'
    OUTWARDLY_PROPAGATING_SPHERICAL_FLAME = 'outwardly propagating spherical flame', 'Outwardly Propagating Spherical Flame'
    HEAT_FLUX_BURNER = 'heat flux burner', 'Heat Flux Burner'


class ExperimentType(models.TextChoices):
    """Types of experiments"""
    IGNITION_DELAY = 'ignition delay', 'Ignition Delay'
    LAMINAR_BURNING_VELOCITY = 'laminar burning velocity measurement', 'Laminar Burning Velocity Measurement'
    JSR_MEASUREMENT = 'jet stirred reactor measurement', 'Jet Stirred Reactor Measurement'
    OUTLET_CONCENTRATION = 'outlet concentration measurement', 'Outlet Concentration Measurement'
    CONCENTRATION_TIME_PROFILE = 'concentration time profile measurement', 'Concentration Time Profile Measurement'
    BSFS_MEASUREMENT = 'burner stabilized flame speciation measurement', 'Burner Stabilized Flame Speciation Measurement'
    RATE_COEFFICIENT = 'rate coefficient', 'Rate Coefficient'
    THERMOCHEMICAL = 'thermochemical', 'Thermochemical'


class IgnitionTarget(models.TextChoices):
    """Target species/property for ignition detection"""
    TEMPERATURE = 'temperature', 'Temperature'
    PRESSURE = 'pressure', 'Pressure'
    OH = 'OH', 'OH'
    OH_STAR = 'OH*', 'OH*'
    CH = 'CH', 'CH'
    CH_STAR = 'CH*', 'CH*'
    NH3 = 'NH3', 'NH3'
    CHEX = 'CHEX', 'CHEX'
    OHEX = 'OHEX', 'OHEX'
    CO2 = 'CO2', 'CO2'
    N2O = 'N2O', 'N2O'
    CH4 = 'CH4', 'CH4'


class IgnitionType(models.TextChoices):
    """Method of detecting ignition"""
    DDT_MAX = 'd/dt max', 'd/dt max'
    MAX = 'max', 'max'
    HALF_MAX = '1/2 max', '1/2 max'
    MIN = 'min', 'min'
    DDT_MAX_EXTRAPOLATED = 'd/dt max extrapolated', 'd/dt max extrapolated'
    DDT_MIN_EXTRAPOLATED = 'd/dt min extrapolated', 'd/dt min extrapolated'
    RELATIVE_CONCENTRATION = 'relative concentration', 'Relative Concentration'
    RELATIVE_INCREASE = 'relative increase', 'Relative Increase'


class CompositionKind(models.TextChoices):
    """Units for composition specification"""
    MOLE_FRACTION = 'mole fraction', 'Mole Fraction'
    MASS_FRACTION = 'mass fraction', 'Mass Fraction'
    MOLE_PERCENT = 'mole percent', 'Mole Percent'


class UncertaintyType(models.TextChoices):
    """Types of uncertainty specification"""
    ABSOLUTE = 'absolute', 'Absolute'
    RELATIVE = 'relative', 'Relative'


class TimeHistoryType(models.TextChoices):
    """Types of time history data"""
    VOLUME = 'volume', 'Volume'
    TEMPERATURE = 'temperature', 'Temperature'
    PRESSURE = 'pressure', 'Pressure'
    PISTON_POSITION = 'piston position', 'Piston Position'
    LIGHT_EMISSION = 'light emission', 'Light Emission'
    OH_EMISSION = 'OH emission', 'OH Emission'
    ABSORPTION = 'absorption', 'Absorption'


class ApparatusMode(models.TextChoices):
    """Apparatus operating mode"""
    REFLECTED_SHOCK = 'reflected shock', 'Reflected Shock'
    INCIDENT_SHOCK = 'incident shock', 'Incident Shock'
    LAMINAR = 'laminar', 'Laminar'
    BURNER_STABILIZED = 'burner stabilized', 'Burner Stabilized'
    CONSTANT_VOLUME_COMBUSTION_CHAMBER = 'constant volume combustion chamber', 'Constant Volume Combustion Chamber'
    PREMIXED = 'premixed', 'Premixed'
    UNSTRETCHED = 'unstretched', 'Unstretched'
    EXTRAPOLATION_ZERO_STRETCH_LS = 'extrapolation method to zero stretch : LS', 'Extrapolation to Zero Stretch (LS)'
    EXTRAPOLATION_ZERO_STRETCH_NQ = 'extrapolation method to zero stretch : NQ', 'Extrapolation to Zero Stretch (NQ)'
    COUNTERFLOW = 'counterflow', 'Counterflow'
    OPF = 'OPF', 'OPF'
    HFM = 'HFM', 'HFM'
    CTF = 'CTF', 'CTF'
    SFF = 'SFF', 'SFF'


class PropertySourceType(models.TextChoices):
    """How a property value was obtained"""
    REPORTED = 'reported', 'Reported'
    ESTIMATED = 'estimated', 'Estimated'
    CALCULATED = 'calculated', 'Calculated'
    DIGITIZED = 'digitized', 'Digitized'


class EvaluatedStandardDeviationMethod(models.TextChoices):
    """Method used to evaluate standard deviation"""
    GENERIC_UNCERTAINTY = 'generic uncertainty', 'Generic Uncertainty'
    COMBINED_SCATTER_REPORTED = 'combined from scatter and reported uncertainty', 'Combined from Scatter and Reported Uncertainty'
    STATISTICAL_SCATTER = 'statistical scatter', 'Statistical Scatter'


class TimeShiftType(models.TextChoices):
    """Time shift reference method for concentration time profile measurement"""
    HALF_DECREASE = 'half decrease', 'Half Decrease'
    RELATIVE_DECREASE = 'relative decrease', 'Relative Decrease'


class ValueWithUnit(models.Model):
    """
    Generic value-unit container aligned with PyKED value_unit_schema.
    """
    value = models.FloatField(null=True, blank=True)
    value_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Raw value string if provided as text"
    )
    units = models.CharField(max_length=50)

    uncertainty_type = models.CharField(
        max_length=20,
        choices=UncertaintyType.choices,
        blank=True
    )
    uncertainty = models.FloatField(null=True, blank=True)
    uncertainty_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Raw uncertainty string if provided as text"
    )
    upper_uncertainty = models.FloatField(null=True, blank=True)
    lower_uncertainty = models.FloatField(null=True, blank=True)
    sourcetype = models.CharField(
        max_length=20,
        choices=PropertySourceType.choices,
        blank=True,
        help_text="How this value was obtained (reported, estimated, calculated, digitized)"
    )

    # Inline evaluated standard deviation (from PyKED value_unit_schema)
    evaluated_standard_deviation = models.FloatField(null=True, blank=True)
    evaluated_standard_deviation_type = models.CharField(
        max_length=20,
        choices=UncertaintyType.choices,
        blank=True
    )
    evaluated_standard_deviation_sourcetype = models.CharField(
        max_length=100,
        choices=PropertySourceType.choices,
        blank=True,
        help_text="How the evaluated standard deviation was obtained (reported, estimated, calculated, digitized)"
    )
    evaluated_standard_deviation_method = models.CharField(
        max_length=100,
        choices=EvaluatedStandardDeviationMethod.choices,
        blank=True
    )

    class Meta:
        db_table = 'chemked_value_units'

    def __str__(self):
        value = self.value if self.value is not None else self.value_text or "n/a"
        return f"{value} {self.units}"

    def has_uncertainty_data(self):
        return any(
            value is not None and value != ""
            for value in (
                self.uncertainty,
                self.upper_uncertainty,
                self.lower_uncertainty,
                self.uncertainty_type,
            )
        )

    def has_evaluated_standard_deviation_data(self):
        return any(
            value is not None and value != ""
            for value in (
                self.evaluated_standard_deviation,
                self.evaluated_standard_deviation_type,
                self.evaluated_standard_deviation_sourcetype,
                self.evaluated_standard_deviation_method,
            )
        )


class FileAuthor(models.Model):
    """
    Author of a ChemKED file (person who digitized/created the data file).
    Distinct from paper/reference authors.
    """
    name = models.CharField(max_length=255)
    orcid = models.CharField(
        max_length=50, 
        blank=True, 
        db_index=True,
        help_text="ORCID identifier (e.g., 0000-0003-4425-7097)"
    )
    person = models.ForeignKey(
        "provenance.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    
    class Meta:
        db_table = 'chemked_file_authors'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_file_author_name'),
        ]
    
    def __str__(self):
        if self.orcid:
            return f"{self.name} ({self.orcid})"
        return self.name


class ReferenceAuthor(models.Model):
    """
    Author of the literature reference (paper authors).
    """
    name = models.CharField(max_length=255)
    orcid = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="ORCID identifier (if available)"
    )
    person = models.ForeignKey(
        "provenance.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = 'chemked_reference_authors'
        unique_together = ['name', 'orcid']

    def __str__(self):
        if self.orcid:
            return f"{self.name} ({self.orcid})"
        return self.name


class Apparatus(models.Model):
    """
    Experimental apparatus used for experiments.
    Examples: Stanford shock tube, UM RCF (rapid compression facility)
    """
    kind = models.CharField(
        max_length=50,
        choices=ApparatusKind.choices,
        help_text="Type of apparatus"
    )
    mode = models.CharField(
        max_length=100,
        choices=ApparatusMode.choices,
        blank=True,
        db_column='operating_mode',
        help_text="Operating mode (e.g., 'reflected shock', 'premixed')"
    )
    institution = models.CharField(max_length=255, blank=True)
    institution_ref = models.ForeignKey(
        "provenance.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apparatus",
    )
    facility = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Specific facility name (e.g., 'low pressure shock tube')"
    )
    
    class Meta:
        db_table = 'chemked_apparatus'
        verbose_name_plural = 'Apparatus'
        unique_together = ['kind', 'institution', 'facility']
    
    def __str__(self):
        parts = [self.get_kind_display()]
        if self.institution:
            parts.append(f"@ {self.institution}")
        if self.facility:
            parts.append(f"({self.facility})")
        return ' '.join(parts)

    @property
    def sssom_slug(self):
        """Deterministic slug for the minted ``promapp:`` node identity.

        Built from the unique_together basis (kind, institution, facility),
        falling back to the linked institution's name when the free-text
        institution is blank, so the generator and linker agree on one slug.
        """
        institution = self.institution or (
            self.institution_ref.name if self.institution_ref else ""
        )
        parts = [self.kind, institution, self.facility]
        joined = "-".join(p for p in parts if p).lower()
        return re.sub(r"[^a-z0-9]+", "-", joined).strip("-")


class ExperimentDataset(models.Model):
    """
    A ChemKED dataset - corresponds to one YAML file.
    Contains metadata and links to individual datapoints.
    """
    # File identification
    chemked_file_path = models.CharField(
        max_length=500, 
        unique=True,
        help_text="Original file path in ChemKED-database"
    )
    file_version = models.IntegerField(default=0)
    chemked_version = models.CharField(max_length=20, default='0.4.1')
    
    # Experiment metadata
    experiment_type = models.CharField(
        max_length=100,
        choices=ExperimentType.choices,
        default=ExperimentType.IGNITION_DELAY
    )
    apparatus = models.ForeignKey(
        Apparatus, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='datasets'
    )
    
    # File authors (who created the ChemKED file)
    file_authors = models.ManyToManyField(
        FileAuthor, 
        related_name='datasets',
        blank=True
    )
    
    # Reference (link to existing Source model in database app)
    reference = models.ForeignKey(
        'database.Source', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='chemked_datasets'
    )
    # Store reference details if Source not linked
    reference_doi = models.CharField(max_length=255, blank=True, db_index=True)
    reference_journal = models.CharField(max_length=255, blank=True)
    reference_year = models.IntegerField(null=True, blank=True)
    reference_volume = models.IntegerField(null=True, blank=True)
    reference_pages = models.CharField(max_length=100, blank=True)
    reference_detail = models.TextField(blank=True)
    reference_authors = models.ManyToManyField(
        ReferenceAuthor,
        related_name='datasets',
        blank=True
    )
    # Additional reference info from ReSpecTh
    reference_title = models.TextField(
        blank=True,
        help_text="Full title of the reference paper"
    )
    reference_figure = models.CharField(
        max_length=255,
        blank=True,
        help_text="Figure reference (e.g., 'Fig. 2')"
    )
    reference_table = models.CharField(
        max_length=255,
        blank=True,
        help_text="Table reference (e.g., 'Table I')"
    )
    reference_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Location in reference (e.g., 'Main article')"
    )
    
    # ReSpecTh file metadata
    file_doi = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="File DOI (e.g., 10.24388/x00002001)"
    )
    respecth_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="ReSpecTh schema version (e.g., 2.3)"
    )
    first_publication_date = models.DateField(
        null=True,
        blank=True,
        help_text="First publication date of the data file"
    )
    last_modification_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last modification date of the data file"
    )
    
    # Experimental method and comments
    method = models.TextField(
        blank=True,
        help_text="Experimental or computational method description"
    )
    comments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of comments from the data file"
    )
    
    # Validation
    is_valid = models.BooleanField(default=True)
    validation_errors = models.JSONField(default=list, blank=True)
    
    # FAIR metadata
    license = models.ForeignKey(
        "provenance.License",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="datasets",
    )
    data_repository_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chemked_datasets'
        ordering = ['reference_year', 'chemked_file_path']
    
    def __str__(self):
        return f"{self.chemked_file_path} ({self.datapoints.count()} points)"
    
    @property
    def short_name(self):
        """Return a shortened display name for the dataset."""
        if self.chemked_file_path:
            # e.g., "n-heptane/Vermeer 1972/st_vermeer_1972.yaml" -> "Vermeer 1972"
            parts = self.chemked_file_path.split('/')
            if len(parts) >= 2:
                return parts[-2]  # Author Year folder
            return parts[-1].replace('.yaml', '')
        return f"Dataset {self.pk}"

    @property
    def fuel_species(self):
        """Extract primary fuel species from composition"""
        # Get composition from first datapoint or common properties
        composition = None
        if hasattr(self, 'common_properties') and self.common_properties:
            composition = self.common_properties.composition
        if not composition and self.datapoints.exists():
            composition = self.datapoints.first().composition
        
        if not composition:
            return []

        species = composition.species.all()
        # Exclude common oxidizers and diluents
        excluded = {'O2', 'N2', 'Ar', 'He', 'CO2', 'H2O'}
        return [s.species_name for s in species if s.species_name not in excluded]


class ExperimentDatapoint(models.Model):
    """
    Individual experimental datapoint from a ChemKED file.
    Stores conditions and measured values.
    """
    dataset = models.ForeignKey(
        ExperimentDataset, 
        on_delete=models.CASCADE,
        related_name='datapoints'
    )
    
    # Primary conditions (stored in SI units internally)
    temperature = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Temperature in Kelvin"
    )
    temperature_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='temperature_datapoints'
    )
    
    pressure = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Pressure in Pascals"
    )
    pressure_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pressure_datapoints'
    )
    
    # Equivalence ratio
    equivalence_ratio = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Fuel-air equivalence ratio (phi)"
    )
    equivalence_ratio_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equivalence_ratio_datapoints'
    )
    
    # Spatial position (for flame/flow reactor profiles)
    position = models.FloatField(
        null=True,
        blank=True,
        help_text="Spatial position (distance from burner, position along reactor) in meters"
    )
    position_units = models.CharField(
        max_length=20,
        blank=True,
        default='m',
        help_text="Original units for position (mm, cm, m)"
    )
    
    # Residence time (for JSR/flow reactor time-series data)
    residence_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Residence time in seconds (for time-series experiments)"
    )
    residence_time_units = models.CharField(
        max_length=20,
        blank=True,
        default='s',
        help_text="Original units for residence time"
    )
    
    composition = models.ForeignKey(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datapoints'
    )
    
    class Meta:
        db_table = 'chemked_datapoints'
        ordering = ['dataset', 'temperature']

    def __str__(self):
        return f"T={self.temperature}K, P={self.pressure/1e5:.5f}bar"
    
    def get_composition(self):
        """Get composition, falling back to dataset common composition"""
        if self.composition:
            return self.composition
        if hasattr(self.dataset, 'common_properties') and self.dataset.common_properties:
            return self.dataset.common_properties.composition
        return None

    def get_composition_kind(self):
        """Get composition kind, falling back to dataset common properties"""
        composition = self.get_composition()
        return composition.kind if composition else None
    
    def get_ignition_target(self):
        """Get ignition target from ignition-delay extension (if present)."""
        if hasattr(self, 'ignition_delay'):
            return self.ignition_delay.get_ignition_target()
        return None

    def get_ignition_type(self):
        """Get ignition type from ignition-delay extension (if present)."""
        if hasattr(self, 'ignition_delay'):
            return self.ignition_delay.get_ignition_type()
        return None

class IgnitionDelayDatapoint(models.Model):
    """
    Ignition-delay-specific fields for a datapoint.
    Keeps ExperimentDatapoint generic for other experiment types.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='ignition_delay'
    )

    ignition_delay = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Ignition delay in seconds"
    )
    ignition_delay_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ignition_delays'
    )

    first_stage_ignition_delay = models.FloatField(
        null=True,
        blank=True,
        help_text="First stage ignition delay in seconds"
    )
    first_stage_ignition_delay_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='first_stage_ignition_delays'
    )

    ignition_target = models.CharField(
        max_length=20,
        choices=IgnitionTarget.choices,
        blank=True,
        help_text="Overrides dataset common ignition target if set"
    )
    ignition_type = models.CharField(
        max_length=50,
        choices=IgnitionType.choices,
        blank=True,
        help_text="Overrides dataset common ignition type if set"
    )

    # Pressure rise (for shock tube experiments)
    pressure_rise = models.FloatField(
        null=True,
        blank=True,
        help_text="Pressure rise rate in 1/s"
    )
    pressure_rise_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ignition_pressure_rises'
    )

    class Meta:
        db_table = 'chemked_ignition_delay'
        verbose_name = 'Ignition Delay Datapoint'
        verbose_name_plural = 'Ignition Delay Datapoints'

    def __str__(self):
        tau_ms = self.ignition_delay * 1000 if self.ignition_delay is not None else None
        tau_str = f"{tau_ms:.2f}ms" if tau_ms is not None else "n/a"
        return f"Ignition delay τ={tau_str}"

    def __float__(self):
        return float(self.ignition_delay) if self.ignition_delay is not None else 0.0

    def get_ignition_target(self):
        if self.ignition_target:
            return self.ignition_target
        if hasattr(self.datapoint.dataset, 'common_properties') and self.datapoint.dataset.common_properties:
            return self.datapoint.dataset.common_properties.ignition_target
        return None

    def get_ignition_type(self):
        if self.ignition_type:
            return self.ignition_type
        if hasattr(self.datapoint.dataset, 'common_properties') and self.datapoint.dataset.common_properties:
            return self.datapoint.dataset.common_properties.ignition_type
        return None


class LaminarBurningVelocityMeasurementDatapoint(models.Model):
    """
    Laminar burning velocity measurement datapoint.
    Stores burning velocity data from flame experiments.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='laminar_burning_velocity_measurement'
    )

    laminar_burning_velocity = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Laminar burning velocity in m/s"
    )
    laminar_burning_velocity_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='laminar_burning_velocities'
    )

    stretch = models.FloatField(
        null=True,
        blank=True,
        help_text="Flame stretch rate in 1/s"
    )
    stretch_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flame_stretch_rates'
    )

    # Pressure rise (optional, from schema)
    pressure_rise = models.FloatField(
        null=True,
        blank=True,
        help_text="Pressure rise rate in 1/s"
    )
    pressure_rise_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lbv_pressure_rises'
    )

    class Meta:
        db_table = 'chemked_laminar_burning_velocity_measurement'
        verbose_name = 'Laminar Burning Velocity Measurement Datapoint'
        verbose_name_plural = 'Laminar Burning Velocity Measurement Datapoints'

    def __str__(self):
        if self.laminar_burning_velocity is None:
            return "Laminar burning velocity (n/a)"
        return f"Laminar burning velocity {self.laminar_burning_velocity:.3f} m/s"


class MeasurementType(models.TextChoices):
    """Type of measured quantity from kdetermination files"""
    RATE_COEFFICIENT = 'rate coefficient', 'Rate Coefficient'
    BRANCHING_RATIO = 'branching ratio', 'Branching Ratio'


class RateCoefficientDatapoint(models.Model):
    """
    Measured quantity data for kdetermination files.
    Stores rate coefficient or branching ratio values at different temperatures.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='rate_coefficient'
    )

    # What was measured
    measurement_type = models.CharField(
        max_length=30,
        choices=MeasurementType.choices,
        default=MeasurementType.RATE_COEFFICIENT,
        help_text="Type of measured quantity (rate coefficient, branching ratio)"
    )
    
    # Measured value
    rate_coefficient = models.FloatField(
        null=True,
        blank=True,
        help_text="Rate coefficient value"
    )
    rate_coefficient_units = models.CharField(
        max_length=50,
        blank=True,
        default='cm3 mol-1 s-1',
        help_text="Units for rate coefficient (e.g., cm3 mol-1 s-1)"
    )
    rate_coefficient_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rate_coefficient_datapoints',
        help_text="Rich value container with uncertainty and evaluated standard deviation"
    )
    
    # Reaction information
    reaction = models.CharField(
        max_length=500,
        blank=True,
        help_text="Reaction equation (e.g., NO2 + HO2 = HNO2 + O2)"
    )
    reaction_order = models.IntegerField(
        null=True,
        blank=True,
        help_text="Overall reaction order"
    )
    bulk_gas = models.CharField(
        max_length=50,
        blank=True,
        help_text="Bulk gas (e.g., N2, Ar)"
    )
    
    # Method used
    method = models.CharField(
        max_length=255,
        blank=True,
        help_text="Experimental or computational method (e.g., ab initio CBS-QB3)"
    )
    
    class Meta:
        db_table = 'chemked_rate_coefficient'
        verbose_name = 'Rate Coefficient Datapoint'
        verbose_name_plural = 'Rate Coefficient Datapoints'

    def __str__(self):
        if self.rate_coefficient is None:
            return "Rate coefficient (n/a)"
        return f"k = {self.rate_coefficient:.2e} {self.rate_coefficient_units}"


class ConcentrationTimeProfileMeasurementDatapoint(models.Model):
    """
    Concentration time profile measurement datapoint.
    Stores species concentration vs. time data from shock tube or flow reactor experiments.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='concentration_time_profile_measurement'
    )

    # Tracked species (link to CompositionSpecies for proper identification)
    tracked_species = models.ForeignKey(
        'CompositionSpecies',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concentration_time_profiles',
        help_text="Species being tracked over time"
    )

    time_units = models.CharField(max_length=20, default='s')
    quantity_units = models.CharField(
        max_length=50,
        help_text="Species concentration units (e.g., mole fraction, ppm)"
    )

    values = models.JSONField(
        help_text="Array of [time, value] or [time, value, uncertainty] pairs"
    )

    uncertainty_type = models.CharField(
        max_length=20,
        choices=UncertaintyType.choices,
        blank=True
    )
    uncertainty_value = models.FloatField(null=True, blank=True)

    # Time shift reference (for defining t=0)
    timeshift_target = models.CharField(
        max_length=255,
        blank=True,
        help_text="Species name used as time shift reference"
    )
    timeshift_type = models.CharField(
        max_length=30,
        choices=TimeShiftType.choices,
        blank=True,
        help_text="Method for determining time shift"
    )
    timeshift_amount = models.FloatField(
        null=True,
        blank=True,
        help_text="Time shift amount in time_units"
    )
    timeshift_amount_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctpm_timeshift_amounts'
    )

    class Meta:
        db_table = 'chemked_concentration_time_profile_measurement'
        verbose_name = 'Concentration Time Profile Measurement Datapoint'
        verbose_name_plural = 'Concentration Time Profile Measurement Datapoints'

    def __str__(self):
        species = self.tracked_species.species_name if self.tracked_species else 'unknown'
        count = len(self.values) if self.values else 0
        return f"Concentration time profile: {species} ({count} points)"


class ConcentrationProfile(models.Model):
    """
    Individual species concentration profile within a CTP measurement datapoint.
    The schema allows multiple concentration-profiles per datapoint (one per tracked species).
    """
    measurement = models.ForeignKey(
        ConcentrationTimeProfileMeasurementDatapoint,
        on_delete=models.CASCADE,
        related_name='concentration_profiles'
    )

    species = models.ForeignKey(
        'CompositionSpecies',
        on_delete=models.SET_NULL,
        null=True,
        related_name='concentration_profiles',
        help_text="Tracked species for this concentration profile"
    )

    time_units = models.CharField(max_length=20, default='s')
    quantity_units = models.CharField(
        max_length=50,
        help_text="Species concentration units (e.g., mole fraction, ppm)"
    )

    values = models.JSONField(
        help_text="Array of [time, value] or [time, value, uncertainty] pairs"
    )

    class Meta:
        db_table = 'chemked_concentration_profiles'

    def __str__(self):
        count = len(self.values) if self.values else 0
        return f"{self.species.species_name} ({count} points)"


class JetStirredReactorMeasurementDatapoint(models.Model):
    """
    Jet stirred reactor measurement datapoint.
    Stores species composition vs. temperature at steady state.
    Common properties (volume, pressure, residence time) come from CommonProperties.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='jet_stirred_reactor_measurement'
    )

    # Measured output composition at this datapoint's conditions
    measured_composition = models.ForeignKey(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jsr_measurement_datapoints',
        help_text="Measured species compositions at this T/P condition"
    )

    # Per-datapoint environment temperature (optional, from schema)
    environment_temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="Environment temperature in Kelvin"
    )
    environment_temperature_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jsr_environment_temperatures'
    )

    class Meta:
        db_table = 'chemked_jet_stirred_reactor_measurement'
        verbose_name = 'Jet Stirred Reactor Measurement Datapoint'
        verbose_name_plural = 'Jet Stirred Reactor Measurement Datapoints'

    def __str__(self):
        return f"JSR measurement at T={self.datapoint.temperature}K"


class OutletConcentrationMeasurementDatapoint(models.Model):
    """
    Outlet concentration measurement datapoint.
    Stores species compositions at reactor outlet for different conditions.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='outlet_concentration_measurement'
    )

    # Measured output composition at this datapoint's conditions
    measured_composition = models.ForeignKey(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocm_datapoints',
        help_text="Measured species compositions at outlet"
    )

    # Per-datapoint residence time override (may differ from common properties)
    residence_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Residence time in seconds (per-datapoint override)"
    )
    residence_time_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocm_residence_times'
    )

    # Volumetric flow in reference state
    volumetric_flow_in_reference_state = models.FloatField(
        null=True,
        blank=True,
        help_text="Volumetric flow rate at reference conditions (m³/s)"
    )
    volumetric_flow_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocm_volumetric_flows'
    )

    # Optional initial composition if different from common properties
    initial_composition = models.ForeignKey(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocm_initial_compositions',
        help_text="Initial composition if different from common properties"
    )

    class Meta:
        db_table = 'chemked_outlet_concentration_measurement'
        verbose_name = 'Outlet Concentration Measurement Datapoint'
        verbose_name_plural = 'Outlet Concentration Measurement Datapoints'

    def __str__(self):
        return f"Outlet concentration at T={self.datapoint.temperature}K"


class BurnerStabilizedFlameSpeciationMeasurementDatapoint(models.Model):
    """
    Burner stabilized flame speciation measurement datapoint.
    Stores species profiles as a function of distance from burner.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='burner_stabilized_flame_speciation_measurement'
    )

    # Measured species composition at this distance
    measured_composition = models.ForeignKey(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bsfsm_datapoints',
        help_text="Measured species compositions at this distance"
    )

    # Distance from burner
    distance = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance from burner in meters"
    )
    distance_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bsfsm_distances'
    )

    # Flow rate
    flow_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Mass flow rate in kg m⁻² s⁻¹"
    )
    flow_rate_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bsfsm_flow_rates'
    )

    class Meta:
        db_table = 'chemked_burner_stabilized_flame_speciation_measurement'
        verbose_name = 'Burner Stabilized Flame Speciation Measurement Datapoint'
        verbose_name_plural = 'Burner Stabilized Flame Speciation Measurement Datapoints'

    def __str__(self):
        d_mm = self.distance * 1000 if self.distance is not None else None
        d_str = f"{d_mm:.2f}mm" if d_mm is not None else "n/a"
        return f"BSFS measurement at d={d_str}"


class CommonProperties(models.Model):
    """
    Properties shared across all datapoints in a dataset (ChemKED common-properties).
    """
    dataset = models.OneToOneField(
        ExperimentDataset,
        on_delete=models.CASCADE,
        related_name='common_properties'
    )

    # Composition
    composition = models.OneToOneField(
        'Composition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_properties'
    )

    # Ignition detection
    ignition_target = models.CharField(
        max_length=20,
        choices=IgnitionTarget.choices,
        blank=True
    )
    ignition_type = models.CharField(
        max_length=50,
        choices=IgnitionType.choices,
        blank=True
    )

    # Pressure + pressure rise
    pressure = models.FloatField(
        null=True,
        blank=True,
        help_text="Common pressure in Pa if same for all datapoints"
    )
    pressure_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_pressure_sets'
    )
    pressure_rise = models.FloatField(
        null=True,
        blank=True,
        help_text="Pressure rise rate in 1/s"
    )
    pressure_rise_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_pressure_rise_sets'
    )
    
    # JSR/Flow Reactor common properties
    reactor_volume = models.FloatField(
        null=True,
        blank=True,
        help_text="Reactor volume in m³"
    )
    reactor_volume_units = models.CharField(
        max_length=20,
        default='m3',
        blank=True
    )
    reactor_volume_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_reactor_volume_sets'
    )
    residence_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Residence time in seconds"
    )
    residence_time_units = models.CharField(
        max_length=20,
        default='s',
        blank=True
    )
    residence_time_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_residence_time_sets'
    )
    
    # Equivalence ratio (common for all datapoints)
    equivalence_ratio = models.FloatField(
        null=True,
        blank=True,
        help_text="Fuel-air equivalence ratio (phi)"
    )
    equivalence_ratio_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_equivalence_ratio_sets'
    )

    # Common temperature (for laminar burning velocity measurement, concentration time profile measurement)
    temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="Common temperature in Kelvin if same for all datapoints"
    )
    temperature_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_temperature_sets'
    )

    # Flow rate (for burner stabilized flame speciation measurement)
    flow_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Mass flow rate in kg m⁻² s⁻¹"
    )
    flow_rate_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_flow_rate_sets'
    )

    # Additional common properties from PyKED schema
    laminar_burning_velocity_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_laminar_burning_velocity_sets'
    )
    environment_temperature_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_environment_temperature_sets'
    )
    global_heat_exchange_coefficient_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_heat_exchange_coeff_sets'
    )
    exchange_area_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_exchange_area_sets'
    )
    reactor_length_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_reactor_length_sets'
    )
    reactor_diameter_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_reactor_diameter_sets'
    )
    pressure_in_reference_state_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_pressure_ref_state_sets'
    )
    temperature_in_reference_state_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='common_temperature_ref_state_sets'
    )

    class Meta:
        db_table = 'chemked_common_properties'
        verbose_name_plural = 'Common Properties'

    def __str__(self):
        return f"Common properties for {self.dataset.chemked_file_path}"


class RCMData(models.Model):
    """
    Rapid Compression Machine specific data for a datapoint.
    Stores compressed conditions and machine parameters.
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='rcm_data'
    )
    
    # Compressed conditions
    compressed_temperature = models.FloatField(
        null=True, 
        blank=True,
        help_text="Temperature at end of compression (K)"
    )
    compressed_temperature_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_compressed_temperature'
    )
    
    compressed_pressure = models.FloatField(
        null=True, 
        blank=True,
        help_text="Pressure at end of compression (Pa)"
    )
    compressed_pressure_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_compressed_pressure'
    )
    
    # Machine parameters
    compression_time = models.FloatField(
        null=True, 
        blank=True,
        help_text="Duration of compression stroke (s)"
    )
    compression_time_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_compression_time'
    )
    stroke = models.FloatField(
        null=True, 
        blank=True,
        help_text="Piston stroke length (m)"
    )
    stroke_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_stroke'
    )
    clearance = models.FloatField(
        null=True, 
        blank=True,
        help_text="Clearance at end of compression (m)"
    )
    clearance_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_clearance'
    )
    compression_ratio = models.FloatField(
        null=True, 
        blank=True,
        help_text="Volumetric compression ratio"
    )
    compression_ratio_quantity = models.ForeignKey(
        ValueWithUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rcm_compression_ratio'
    )
    
    class Meta:
        db_table = 'chemked_rcm_data'
        verbose_name = 'RCM Data'
        verbose_name_plural = 'RCM Data'
    
    def __str__(self):
        return f"RCM: Tc={self.compressed_temperature}K, Pc={self.compressed_pressure/1e5:.1f}bar"


class TimeHistory(models.Model):
    """
    Time-dependent data for a datapoint (e.g., volume history for RCM).
    Stores the time series as JSON for efficiency.
    """
    datapoint = models.ForeignKey(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='time_histories'
    )
    
    history_type = models.CharField(
        max_length=30,
        choices=TimeHistoryType.choices,
        help_text="Type of time history data"
    )
    
    # Units for the data
    time_units = models.CharField(max_length=20, default='s')
    quantity_units = models.CharField(max_length=20)
    
    # Time series data as JSON array of [time, value] pairs
    # Or [time, value, uncertainty] if uncertainty per point
    values = models.JSONField(
        null=True,
        blank=True,
        help_text="Array of [time, value] or [time, value, uncertainty] pairs"
    )

    # Optional source filename (when data stored in external file)
    source_filename = models.CharField(max_length=500, blank=True)
    
    # Optional overall uncertainty
    uncertainty_type = models.CharField(
        max_length=20, 
        choices=UncertaintyType.choices,
        blank=True
    )
    uncertainty_value = models.FloatField(null=True, blank=True)
    
    class Meta:
        db_table = 'chemked_time_histories'
        verbose_name = 'Time History'
        verbose_name_plural = 'Time Histories'
    
    def __str__(self):
        count = len(self.values) if self.values else 0
        return f"{self.get_history_type_display()} ({count} points)"
    
    @property
    def num_points(self):
        return len(self.values) if self.values else 0


class VolumeHistory(models.Model):
    """
    Volume history data for RCM experiments (separate schema in ChemKED).
    """
    datapoint = models.OneToOneField(
        ExperimentDatapoint,
        on_delete=models.CASCADE,
        related_name='volume_history'
    )

    time_units = models.CharField(max_length=20, default='s')
    volume_units = models.CharField(max_length=20)

    values = models.JSONField(
        help_text="Array of [time, volume] pairs"
    )

    class Meta:
        db_table = 'chemked_volume_histories'

    def __str__(self):
        return f"Volume history ({len(self.values)} points)"


class Composition(models.Model):
    """
    Composition block for a datapoint or common-properties.
    """
    kind = models.CharField(
        max_length=20,
        choices=CompositionKind.choices
    )

    class Meta:
        db_table = 'chemked_compositions'

    def __str__(self):
        return f"Composition ({self.kind or 'unspecified'})"


class CompositionSpecies(models.Model):
    """
    Individual species in a composition.
    Normalized table for querying by species across datasets.
    Links to database.Species if identified.
    """
    composition = models.ForeignKey(
        Composition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='species'
    )
    
    # Species identification
    species_name = models.CharField(max_length=255, db_index=True)
    chem_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable chemical name (e.g., 'methanol')"
    )
    cas = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="CAS Registry Number"
    )
    inchi = models.CharField(
        max_length=500, 
        blank=True, 
        db_index=True,
        help_text="InChI identifier"
    )
    smiles = models.CharField(max_length=500, blank=True)

    # Optional atomic composition + thermo data
    atomic_composition = models.JSONField(
        null=True,
        blank=True,
        help_text="Atomic composition list of {element, amount}"
    )
    
    # Link to database Species if matched
    database_species = models.ForeignKey(
        'database.Species',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chemked_occurrences'
    )
    
    # Amount
    amount = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Amount (units depend on composition kind)"
    )
    amount_uncertainty = models.FloatField(null=True, blank=True)
    amount_uncertainty_type = models.CharField(
        max_length=20, 
        choices=UncertaintyType.choices,
        blank=True
    )
    amount_upper_uncertainty = models.FloatField(null=True, blank=True)
    amount_lower_uncertainty = models.FloatField(null=True, blank=True)
    amount_uncertainty_sourcetype = models.CharField(
        max_length=100,
        blank=True
    )
    amount_evaluated_standard_deviation = models.FloatField(null=True, blank=True)
    amount_evaluated_standard_deviation_type = models.CharField(
        max_length=20,
        choices=UncertaintyType.choices,
        blank=True
    )
    amount_evaluated_standard_deviation_sourcetype = models.CharField(
        max_length=100,
        blank=True
    )
    amount_evaluated_standard_deviation_method = models.CharField(
        max_length=100,
        choices=EvaluatedStandardDeviationMethod.choices,
        blank=True
    )
    
    class Meta:
        db_table = 'chemked_composition_species'
        ordering = ['-amount']  # Order by amount descending
        constraints = [
            models.UniqueConstraint(
                fields=['composition', 'species_name', 'inchi', 'smiles'],
                name='chemked_unique_species_per_datapoint'
            )
        ]
    
    def __str__(self):
        return f"{self.species_name}: {self.amount}"

    def populate_identifiers(self):
        if not self.inchi:
            return False

        if self.smiles and self.atomic_composition:
            return False

        try:
            from chemked_database.utils.chemistry import (
                infer_smiles_and_atomic_composition,
                rdkit_available,
            )
        except Exception:
            return False

        if not rdkit_available():
            return False

        smiles, atomic = infer_smiles_and_atomic_composition(self.inchi)
        updated = False

        if not self.smiles and smiles:
            self.smiles = smiles
            updated = True
        if not self.atomic_composition and atomic:
            self.atomic_composition = atomic
            updated = True

        return updated

    def save(self, *args, **kwargs):
        self.populate_identifiers()
        super().save(*args, **kwargs)


class SpeciesThermo(models.Model):
    """
    Thermo data for a composition species (separate model from JSON).
    Mirrors the ChemKED/PyKED thermo schema: T_ranges (3 values), data (14 coeffs), note.
    """
    species = models.OneToOneField(
        CompositionSpecies,
        on_delete=models.CASCADE,
        related_name='thermo_data'
    )

    t_range_1 = models.CharField(max_length=50)
    t_range_2 = models.CharField(max_length=50)
    t_range_3 = models.CharField(max_length=50)

    coeff_1 = models.FloatField(null=True, blank=True)
    coeff_2 = models.FloatField(null=True, blank=True)
    coeff_3 = models.FloatField(null=True, blank=True)
    coeff_4 = models.FloatField(null=True, blank=True)
    coeff_5 = models.FloatField(null=True, blank=True)
    coeff_6 = models.FloatField(null=True, blank=True)
    coeff_7 = models.FloatField(null=True, blank=True)
    coeff_8 = models.FloatField(null=True, blank=True)
    coeff_9 = models.FloatField(null=True, blank=True)
    coeff_10 = models.FloatField(null=True, blank=True)
    coeff_11 = models.FloatField(null=True, blank=True)
    coeff_12 = models.FloatField(null=True, blank=True)
    coeff_13 = models.FloatField(null=True, blank=True)
    coeff_14 = models.FloatField(null=True, blank=True)

    note = models.TextField(blank=True)

    class Meta:
        db_table = 'chemked_species_thermo'
        verbose_name = 'Species Thermo'
        verbose_name_plural = 'Species Thermo'

    def __str__(self):
        return f"Thermo for {self.species.species_name}"


class EvaluatedStandardDeviation(models.Model):
    """
    Evaluated standard deviation for a dataset property.
    A dataset can have multiple entries (e.g., one for ignition delay, one per species).
    """
    dataset = models.ForeignKey(
        ExperimentDataset,
        on_delete=models.CASCADE,
        related_name='evaluated_std_deviations'
    )

    reference = models.CharField(
        max_length=100,
        help_text="Property this applies to (e.g., 'ignition delay', 'composition', 'laminar burning velocity')"
    )
    kind = models.CharField(
        max_length=20,
        choices=UncertaintyType.choices,
        help_text="Absolute or relative"
    )
    method = models.CharField(
        max_length=100,
        choices=EvaluatedStandardDeviationMethod.choices,
        help_text="Method used to evaluate"
    )
    value = models.FloatField(
        help_text="Standard deviation value"
    )
    units = models.CharField(
        max_length=50,
        help_text="Units of the standard deviation value"
    )
    sourcetype = models.CharField(
        max_length=100,
        blank=True,
        choices=PropertySourceType.choices,
        help_text="How the standard deviation was obtained"
    )

    # Optional: species-specific standard deviation
    species = models.ForeignKey(
        CompositionSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluated_std_deviations',
        help_text="For species-specific standard deviation (e.g., per-species in BSFSM)"
    )

    class Meta:
        db_table = 'chemked_evaluated_std_deviation'
        verbose_name = 'Evaluated Standard Deviation'
        verbose_name_plural = 'Evaluated Standard Deviations'

    def __str__(self):
        species_str = f" ({self.species.species_name})" if self.species else ""
        return f"σ={self.value} {self.units} [{self.reference}{species_str}]"


class Submission(models.Model):
    """Tracks an upload submission with import results and optional GitHub PR info."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        PARTIAL = 'partial', 'Partial Success'
        FAILED = 'failed', 'Failed'

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Import summary (JSON: lists of {filename, dataset_id, datapoints, error, ...})
    successful_imports = models.JSONField(default=list, blank=True)
    failed_imports = models.JSONField(default=list, blank=True)
    skipped_imports = models.JSONField(default=list, blank=True)

    # Contributor info
    contributor_name = models.CharField(max_length=200, blank=True)
    contributor_orcid = models.CharField(max_length=20, blank=True)

    # GitHub PR info (null when contribute_to_github is False)
    pr_url = models.URLField(blank=True)
    pr_number = models.PositiveIntegerField(null=True, blank=True)
    branch = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'chemked_submission'
        ordering = ['-created_at']

    def __str__(self):
        return f"Submission {self.pk} ({self.status}) – {self.created_at:%Y-%m-%d %H:%M}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('chemked_database:submission-status', kwargs={'pk': self.pk})