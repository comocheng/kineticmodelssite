"""
Analysis Models

Models for storing simulation runs, results, and model-experiment coverage tracking.
Includes the Fuel-Model Compatibility Map for precomputed fuel→model navigation.
"""

import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone


class SimulationStatus(models.TextChoices):
    """Status of a simulation run"""
    PENDING = 'pending', 'Pending'
    QUEUED = 'queued', 'Queued'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class TriggerType(models.TextChoices):
    """What triggered the simulation"""
    MANUAL = 'manual', 'Manual (User)'
    AUTO_MODEL_UPDATE = 'auto_model', 'Auto (Model Updated)'
    AUTO_DATASET_UPDATE = 'auto_dataset', 'Auto (Dataset Updated)'
    SCHEDULED = 'scheduled', 'Scheduled'
    API = 'api', 'API Request'


class MappingMethod(models.TextChoices):
    """How species mapping was determined"""
    SMILES = 'smiles', 'SMILES Match'
    INCHI = 'inchi', 'InChI Match'
    NORMALIZED = 'normalized', 'Normalized Label Match'
    MANUAL = 'manual', 'Manual Override'
    FALLBACK = 'fallback', 'Fallback (Unverified)'


class SimulationRun(models.Model):
    """
    Represents a single PyTeCK simulation run for a model-dataset pair.
    """
    # Core relationships
    kinetic_model = models.ForeignKey(
        'database.KineticModel',
        on_delete=models.CASCADE,
        related_name='simulation_runs'
    )
    dataset = models.ForeignKey(
        'chemked_database.ExperimentDataset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='simulation_runs'
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=SimulationStatus.choices,
        default=SimulationStatus.PENDING,
        db_index=True
    )
    triggered_by = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        default=TriggerType.MANUAL
    )
    triggered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_simulations'
    )

    # Version tracking (for detecting model changes)
    model_version_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of model content at simulation time"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)

    # Configuration used
    skip_validation = models.BooleanField(default=True)
    spec_keys_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Species mapping used for this run"
    )

    # Output directory tracking
    results_dir = models.CharField(
        max_length=512,
        blank=True,
        help_text="Path to simulation results directory"
    )

    class Meta:
        db_table = 'analysis_simulation_run'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kinetic_model', 'dataset']),
            models.Index(fields=['status', 'created_at']),
        ]
        # Allow multiple runs of same model-dataset pair (for re-runs)
        # unique_together is NOT set

    def __str__(self):
        return f"{self.kinetic_model.model_name} × {self.dataset.short_name} ({self.status})"

    @property
    def duration(self):
        """Return simulation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_outdated(self):
        """Check if model has changed since this simulation."""
        if not self.model_version_hash:
            return True
        current_hash = self.compute_model_hash(self.kinetic_model)
        return current_hash != self.model_version_hash

    @staticmethod
    def compute_model_hash(kinetic_model):
        """Compute a hash of the model's content for change detection."""
        # Hash key model attributes that affect simulation
        content = f"{kinetic_model.pk}:{kinetic_model.model_name}"
        
        # Include file modification times if available
        for field_name in ['chemkin_reactions_file', 'chemkin_thermo_file', 'chemkin_transport_file']:
            field = getattr(kinetic_model, field_name, None)
            if field and hasattr(field, 'name') and field.name:
                content += f":{field.name}"

        return hashlib.sha256(content.encode()).hexdigest()

    def mark_running(self):
        """Mark simulation as running."""
        self.status = SimulationStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self):
        """Mark simulation as completed."""
        self.status = SimulationStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def mark_failed(self, error_message, traceback=''):
        """Mark simulation as failed with error details."""
        self.status = SimulationStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = str(error_message)[:2000]
        self.traceback = str(traceback)[:10000]
        self.save(update_fields=['status', 'completed_at', 'error_message', 'traceback'])

    def mark_cancelled(self, reason='Cancelled by user'):
        """Mark simulation as cancelled."""
        self.status = SimulationStatus.CANCELLED
        self.completed_at = timezone.now()
        self.error_message = reason
        self.save(update_fields=['status', 'completed_at', 'error_message'])

    @property
    def is_stale(self):
        """
        Check if a running simulation appears to be stale/stuck.
        A simulation is considered stale if:
        - Status is 'running' AND
        - It started more than 30 minutes ago without completing
        """
        if self.status != SimulationStatus.RUNNING:
            return False
        if not self.started_at:
            # Running but never started - definitely stale
            return True
        from datetime import timedelta
        stale_threshold = timezone.now() - timedelta(minutes=30)
        return self.started_at < stale_threshold

    @classmethod
    def cleanup_stale_runs(cls, dry_run=False):
        """
        Find and mark stale running simulations as failed.
        
        Args:
            dry_run: If True, only return count without modifying
            
        Returns:
            Number of stale runs found/cleaned
        """
        from datetime import timedelta
        stale_threshold = timezone.now() - timedelta(minutes=30)
        
        stale_runs = cls.objects.filter(
            status=SimulationStatus.RUNNING,
            started_at__lt=stale_threshold
        )
        
        # Also include runs that are "running" but never started
        never_started = cls.objects.filter(
            status=SimulationStatus.RUNNING,
            started_at__isnull=True,
            created_at__lt=stale_threshold
        )
        
        stale_count = stale_runs.count() + never_started.count()
        
        if not dry_run:
            for run in stale_runs:
                run.mark_failed('Simulation timed out or was interrupted (stale)')
            for run in never_started:
                run.mark_failed('Simulation never started (stale)')
        
        return stale_count


class SimulationResult(models.Model):
    """
    Aggregated results from a simulation run.
    """
    simulation_run = models.OneToOneField(
        SimulationRun,
        on_delete=models.CASCADE,
        related_name='result'
    )

    # PyTeCK metrics
    average_error_function = models.FloatField(
        null=True,
        blank=True,
        help_text="Average error function value across all datapoints"
    )
    average_deviation_function = models.FloatField(
        null=True,
        blank=True,
        help_text="Average deviation (log ratio) across all datapoints"
    )

    # Raw results storage
    results_yaml = models.TextField(
        blank=True,
        help_text="Raw YAML output from PyTeCK"
    )
    results_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parsed results as JSON"
    )

    # Summary statistics
    num_datapoints = models.PositiveIntegerField(default=0)
    num_successful = models.PositiveIntegerField(default=0)
    num_failed = models.PositiveIntegerField(default=0)

    # Temperature/pressure ranges evaluated
    min_temperature = models.FloatField(null=True, blank=True)
    max_temperature = models.FloatField(null=True, blank=True)
    min_pressure = models.FloatField(null=True, blank=True)
    max_pressure = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'analysis_simulation_result'

    def __str__(self):
        return f"Result for {self.simulation_run}"

    @property
    def error_function_display(self):
        """Format error function for display."""
        if self.average_error_function is not None:
            return f"{self.average_error_function:.2f}"
        return "N/A"

    @property
    def deviation_display(self):
        """Format deviation for display (as orders of magnitude)."""
        if self.average_deviation_function is not None:
            return f"{self.average_deviation_function:.2f}"
        return "N/A"

    @property
    def std_error_function(self):
        """Get standard deviation from results_json (from first dataset)."""
        if self.results_json:
            # Try to get from datasets (PyTeCK stores it per-dataset)
            datasets = self.results_json.get('datasets', [])
            if datasets and len(datasets) > 0:
                return datasets[0].get('standard deviation')
            # Fallback to top-level error function standard deviation
            return self.results_json.get('error function standard deviation')
        return None


class DatapointResult(models.Model):
    """
    Individual datapoint comparison result.
    """
    simulation_result = models.ForeignKey(
        SimulationResult,
        on_delete=models.CASCADE,
        related_name='datapoint_results'
    )
    datapoint = models.ForeignKey(
        'chemked_database.ExperimentDatapoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='simulation_results'
    )

    # Conditions
    temperature = models.FloatField(help_text="Temperature in Kelvin")
    pressure = models.FloatField(help_text="Pressure in Pascal")

    # Composition snapshot
    composition = models.JSONField(
        default=list,
        help_text="Species composition at this datapoint"
    )
    composition_type = models.CharField(max_length=50, default='mole fraction')

    # Ignition delay comparison
    experimental_ignition_delay = models.FloatField(
        help_text="Experimental ignition delay in seconds"
    )
    simulated_ignition_delay = models.FloatField(
        null=True,
        blank=True,
        help_text="Simulated ignition delay in seconds"
    )

    # Error metrics for this point
    error_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Error function value for this datapoint"
    )
    deviation = models.FloatField(
        null=True,
        blank=True,
        help_text="Log deviation (simulated/experimental)"
    )

    # Simulation status for this point
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'analysis_datapoint_result'
        ordering = ['temperature']

    def __str__(self):
        return f"T={self.temperature}K, P={self.pressure/1e5:.1f}bar"

    @property
    def ignition_delay_ratio(self):
        """Ratio of simulated to experimental ignition delay."""
        if self.simulated_ignition_delay and self.experimental_ignition_delay:
            return self.simulated_ignition_delay / self.experimental_ignition_delay
        return None

    @property
    def pressure_atm(self):
        """Pressure converted from Pascal to atm."""
        if self.pressure:
            return self.pressure / 101325.0
        return None

    # Species that are NOT fuels (oxidizers, diluents, products)
    _NON_FUEL_NAMES = frozenset({
        'o2', 'oxygen', 'n2', 'nitrogen', 'ar', 'argon',
        'he', 'helium', 'ne', 'neon', 'kr', 'krypton',
        'co2', 'carbon dioxide', 'h2o', 'water',
    })

    # Known non-carbon fuels and their atomic compositions
    _NON_CARBON_FUELS = {
        'nh3': {'N': 1, 'H': 3},
        'ammonia': {'N': 1, 'H': 3},
        'h2': {'H': 2},
        'hydrogen': {'H': 2},
        'h2s': {'H': 2, 'S': 1},
        'hydrogen sulfide': {'H': 2, 'S': 1},
        'n2h4': {'N': 2, 'H': 4},
        'hydrazine': {'N': 2, 'H': 4},
    }

    @property
    def equivalence_ratio(self):
        """
        Calculate equivalence ratio (φ) from composition.

        φ = Σ(xᵢ · νᵢ) / x_O₂

        where xᵢ is the mole fraction of fuel species *i* and νᵢ is its
        stoichiometric O₂ requirement.

        Supports:
        - Hydrocarbons:       CₙHₘ + (n + m/4) O₂ → …
        - Oxygenated fuels:   CₙHₘOₖ + (n + m/4 − k/2) O₂ → …
        - Hydrogen:           H₂ + ½ O₂ → H₂O
        - Ammonia:            NH₃ + ¾ O₂ → ½ N₂ + 3/2 H₂O
        - Sulphur fuels:      H₂S + 3/2 O₂ → SO₂ + H₂O
        """
        if not self.composition:
            return None

        oxidizer_amount = 0.0
        fuel_entries = []  # list of (amount, atoms_dict)

        for species in self.composition:
            name = species.get('species-name', '').lower().strip()
            try:
                amount = float(species.get('amount', 0))
            except (ValueError, TypeError):
                continue

            if name in self._NON_FUEL_NAMES:
                if name in ('o2', 'oxygen'):
                    oxidizer_amount = amount
                continue

            # Potential fuel — resolve its atomic composition
            atoms = self._parse_atomic_composition(
                species.get('atomic-composition'),
                name,
            )
            if atoms and self._compute_stoich_o2(atoms) > 0:
                fuel_entries.append((amount, atoms))

        if not fuel_entries or oxidizer_amount <= 0:
            return None

        # Sum the stoichiometric O₂ demand weighted by each fuel's amount
        total_stoich_o2 = 0.0
        for amount, atoms in fuel_entries:
            nu = self._compute_stoich_o2(atoms)
            if nu > 0:
                total_stoich_o2 += amount * nu

        if total_stoich_o2 <= 0:
            return None

        return total_stoich_o2 / oxidizer_amount

    @staticmethod
    def _compute_stoich_o2(atoms):
        """
        Compute the stoichiometric O₂ requirement for complete combustion.

        General formula for CₙHₘOₖNⱼSₚ:
            ν_O₂ = n + m/4 − k/2 + p

        Nitrogen is released as N₂ (does not consume O₂).
        Sulphur is oxidised to SO₂ (consumes 1 O₂ per S atom).

        Returns 0.0 if the species has no positive O₂ demand.
        """
        n_c = atoms.get('C', 0)
        n_h = atoms.get('H', 0)
        n_o = atoms.get('O', 0)
        n_s = atoms.get('S', 0)
        nu = n_c + n_h / 4.0 - n_o / 2.0 + n_s
        return max(nu, 0.0)

    @staticmethod
    def _parse_atomic_composition(atomic_data, species_name):
        """
        Return an element→count dict (e.g. ``{'C': 7, 'H': 16}``) from
        structured JSON data or, failing that, by parsing the species name
        as a molecular formula.

        Returns ``None`` when the composition cannot be determined.
        """
        import re

        # 1. Structured data  [{"element": "C", "amount": 7}, …] or {"C": 7, …}
        if atomic_data:
            atoms = {}
            if isinstance(atomic_data, list):
                for entry in atomic_data:
                    elem = entry.get('element', '')
                    count = entry.get('amount', 0)
                    if elem:
                        atoms[elem] = atoms.get(elem, 0) + count
            elif isinstance(atomic_data, dict):
                atoms = dict(atomic_data)
            if atoms:
                return atoms

        # 2. Check known non-carbon fuels by name
        name_lower = species_name.strip().lower()
        known = DatapointResult._NON_CARBON_FUELS.get(name_lower)
        if known:
            return dict(known)

        # 3. Parse formula from species name (e.g. 'c7h16', 'ch3oh', 'nh3')
        name = species_name.strip()
        atoms = {}
        for match in re.finditer(r'([A-Z][a-z]?)(\d*)', name):
            element = match.group(1)
            count = int(match.group(2)) if match.group(2) else 1
            atoms[element] = atoms.get(element, 0) + count

        if atoms:
            return atoms

        return None


class SpeciesMapping(models.Model):
    """
    Cached species name mapping between dataset and model.
    Allows manual overrides and tracks mapping confidence.
    """
    kinetic_model = models.ForeignKey(
        'database.KineticModel',
        on_delete=models.CASCADE,
        related_name='species_mappings'
    )
    dataset = models.ForeignKey(
        'chemked_database.ExperimentDataset',
        on_delete=models.CASCADE,
        related_name='species_mappings',
        null=True,
        blank=True,
        help_text="If null, applies to all datasets"
    )

    # Mapping details
    dataset_species_name = models.CharField(
        max_length=100,
        help_text="Species name as it appears in the dataset"
    )
    model_species_name = models.CharField(
        max_length=100,
        help_text="Corresponding species name in the kinetic model"
    )

    # How the mapping was determined
    mapping_method = models.CharField(
        max_length=20,
        choices=MappingMethod.choices,
        default=MappingMethod.FALLBACK
    )
    confidence = models.FloatField(
        default=0.5,
        help_text="Confidence score 0-1"
    )

    # For manual overrides
    is_manual_override = models.BooleanField(default=False)
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    override_reason = models.CharField(max_length=200, blank=True)

    # Identifiers used for matching
    smiles = models.CharField(max_length=500, blank=True)
    inchi = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analysis_species_mapping'
        unique_together = ['kinetic_model', 'dataset', 'dataset_species_name']
        indexes = [
            models.Index(fields=['kinetic_model', 'dataset_species_name']),
        ]

    def __str__(self):
        return f"{self.dataset_species_name} → {self.model_species_name}"


class ModelDatasetCoverage(models.Model):
    """
    Denormalized table tracking which model-dataset pairs have been evaluated.
    Updated automatically via signals when SimulationRuns complete.
    """
    kinetic_model = models.ForeignKey(
        'database.KineticModel',
        on_delete=models.CASCADE,
        related_name='dataset_coverage'
    )
    dataset = models.ForeignKey(
        'chemked_database.ExperimentDataset',
        on_delete=models.CASCADE,
        related_name='model_coverage'
    )

    # Latest successful run
    latest_run = models.ForeignKey(
        SimulationRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )

    # Cached metrics from latest run
    latest_error_function = models.FloatField(null=True, blank=True)
    latest_deviation = models.FloatField(null=True, blank=True)

    # Status flags
    has_successful_run = models.BooleanField(default=False)
    is_outdated = models.BooleanField(
        default=False,
        help_text="True if model changed since last run"
    )
    needs_rerun = models.BooleanField(
        default=False,
        help_text="Flagged for re-evaluation"
    )

    # Run counts
    total_runs = models.PositiveIntegerField(default=0)
    successful_runs = models.PositiveIntegerField(default=0)
    failed_runs = models.PositiveIntegerField(default=0)

    # Timestamps
    first_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'analysis_model_dataset_coverage'
        unique_together = ['kinetic_model', 'dataset']
        indexes = [
            models.Index(fields=['has_successful_run', 'is_outdated']),
        ]

    def __str__(self):
        status = "✓" if self.has_successful_run else "✗"
        return f"{status} {self.kinetic_model.model_name} × {self.dataset.short_name}"

    def update_from_run(self, simulation_run):
        """Update coverage record from a completed simulation run."""
        self.total_runs += 1
        self.last_evaluated_at = simulation_run.completed_at

        if not self.first_evaluated_at:
            self.first_evaluated_at = simulation_run.completed_at

        if simulation_run.status == SimulationStatus.COMPLETED:
            self.successful_runs += 1
            self.has_successful_run = True
            self.latest_run = simulation_run
            self.is_outdated = False
            self.needs_rerun = False

            # Cache metrics
            if hasattr(simulation_run, 'result'):
                self.latest_error_function = simulation_run.result.average_error_function
                self.latest_deviation = simulation_run.result.average_deviation_function
        else:
            self.failed_runs += 1

        self.save()


# ===========================================================================
# Fuel-Model Compatibility Map
# ===========================================================================

class FuelGroup(models.Model):
    """
    Optional grouping of structurally related fuels (e.g., butanol isomers,
    C7 alkanes, primary reference fuels).

    Groups can be auto-generated by molecular formula or hand-curated.
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Display name, e.g. 'butanol isomers'"
    )
    formula = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Shared molecular formula, e.g. 'C4H10O'"
    )
    description = models.TextField(blank=True)
    is_auto = models.BooleanField(
        default=True,
        help_text="True if group was auto-generated from formula"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first"
    )

    class Meta:
        db_table = 'analysis_fuel_group'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class FuelSpecies(models.Model):
    """
    Canonical fuel species extracted from experiment datasets.

    Each row is a unique fuel identified by its InChI.  The table is rebuilt
    by ``rebuild_fuel_map`` whenever new datasets are imported.
    """
    # Canonical identifiers
    inchi = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="Standard InChI (canonical key)"
    )
    smiles = models.CharField(
        max_length=500,
        blank=True,
        help_text="Canonical SMILES"
    )
    formula = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Molecular formula, e.g. 'C7H16'"
    )
    common_name = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        help_text="Human-friendly name chosen from dataset species_name"
    )

    # All name variants found across datasets
    name_variants = models.JSONField(
        default=list,
        blank=True,
        help_text="List of all species_name strings seen for this InChI"
    )

    # Optional grouping
    group = models.ForeignKey(
        FuelGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuels'
    )

    # Precomputed counts (denormalized for fast listing)
    dataset_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of experiment datasets using this fuel"
    )
    compatible_model_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of kinetic models that contain this species"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analysis_fuel_species'
        verbose_name_plural = 'fuel species'
        ordering = ['-dataset_count', 'common_name']

    def __str__(self):
        return self.common_name or self.smiles or self.inchi


class FuelModelCompatibility(models.Model):
    """
    Precomputed compatibility record for a (fuel, kinetic_model) pair.

    Stores whether the fuel can be found in the model's species list and
    caches the species-name mapping snapshot so the Fuel-Model Map page
    loads instantly without re-running RDKit at request time.
    """
    fuel = models.ForeignKey(
        FuelSpecies,
        on_delete=models.CASCADE,
        related_name='model_compatibilities'
    )
    kinetic_model = models.ForeignKey(
        'database.KineticModel',
        on_delete=models.CASCADE,
        related_name='fuel_compatibilities'
    )

    # Whether the fuel species was found in the model
    is_compatible = models.BooleanField(
        default=False,
        db_index=True
    )

    # The model species name that matched the fuel
    matched_model_species = models.CharField(
        max_length=200,
        blank=True,
        help_text="Species name in the model that matched this fuel"
    )
    match_method = models.CharField(
        max_length=20,
        choices=MappingMethod.choices,
        default=MappingMethod.FALLBACK
    )

    # Model-level stats (denormalized)
    model_total_species = models.PositiveIntegerField(
        default=0,
        help_text="Total species count in the model"
    )
    model_total_reactions = models.PositiveIntegerField(
        default=0,
        help_text="Total reaction count in the model"
    )

    # Snapshot of full species mapping for the datasets this fuel appears in
    # Format: {"dataset_species_name": "model_species_name", ...}
    species_mapping_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached species mapping for preview"
    )

    # Link to latest simulation result if one exists
    latest_coverage = models.ForeignKey(
        ModelDatasetCoverage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text="Best coverage record for any dataset with this fuel"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analysis_fuel_model_compatibility'
        unique_together = ['fuel', 'kinetic_model']
        indexes = [
            models.Index(fields=['fuel', 'is_compatible']),
        ]

    def __str__(self):
        icon = "✓" if self.is_compatible else "✗"
        return f"{icon} {self.fuel} ↔ {self.kinetic_model.model_name}"
