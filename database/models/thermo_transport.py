from math import log

from django.db import models
from django.contrib.postgres.fields import ArrayField
from rmgpy.constants import R as gas_constant


STANDARD_STATE_TEMPERATURE = 298.15
STANDARD_STATE_TEMPERATURE_TOLERANCE = 2.0


class ThermoRecord(models.Model):
    """Versioned source data, including references without a heat-capacity curve."""

    class Provider(models.TextChoices):
        ATCT = "atct", "ATcT"
        BURCAT = "burcat", "Burcat"
        GROUP_ADDITIVITY = "group_additivity", "Group Additivity"
        # Derived here, never looked up: ATcT enthalpy on a Burcat or group-additivity Cp/S curve.
        ATCT_CONSTRAINED = "atct_constrained", "ATcT-constrained RMG thermo"
        # Entries of RMG-database thermo libraries other than BurcatNS (match_rmg_libraries).
        RMG_THERMO_LIBRARY = "rmg_thermo_library", "RMG-database thermo library"

    # Providers with their own lookup jobs.
    SOURCE_PROVIDERS = (Provider.ATCT.value, Provider.BURCAT.value, Provider.GROUP_ADDITIVITY.value)

    species = models.ForeignKey("Species", on_delete=models.CASCADE, related_name="thermo_records")
    structure = models.ForeignKey("Structure", on_delete=models.PROTECT, related_name="thermo_records")
    provider = models.CharField(max_length=24, choices=Provider.choices, db_index=True)
    external_id = models.CharField(max_length=500)
    source_version = models.CharField(max_length=100)
    label = models.CharField(max_length=500)
    phase = models.CharField(max_length=20, default="gas")
    electronic_state = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    enthalpy_0 = models.FloatField(null=True, blank=True, help_text="Formation enthalpy, J/mol")
    enthalpy_298 = models.FloatField(null=True, blank=True, help_text="Formation enthalpy at 298.15 K, J/mol")
    uncertainty_298 = models.FloatField(null=True, blank=True, help_text="Reported uncertainty, J/mol; see source convention")
    entropy_298 = models.FloatField(null=True, blank=True, help_text="Entropy at 298.15 K, J/(mol K)")
    nasa_thermo = models.OneToOneField("Thermo", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="provider_record")
    # For derived records: where the 298.15 K enthalpy and the Cp(T)/S(T) curve came from.
    enthalpy_source = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                                        related_name="constrained_by_enthalpy")
    heat_capacity_source = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                                             related_name="constrained_by_heat_capacity")
    provenance = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    retrieved_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("provider", "external_id", "-retrieved_at")
        constraints = [models.UniqueConstraint(
            fields=("provider", "external_id", "source_version"), name="unique_versioned_thermo_record")]

    def __str__(self):
        return f"{self.get_provider_display()}: {self.label} ({self.source_version})"

    @property
    def enthalpy_shift_kj(self):
        """ATcT-constrained thermo only: how far the Cp/S source's own H298 was moved, kJ/mol."""
        shift = self.raw_data.get("enthalpy_shift_J_mol") if self.provider == self.Provider.ATCT_CONSTRAINED else None
        return None if shift is None else shift / 1000


class ThermoEnrichmentJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Available"
        NO_MATCH = "no_match", "No matching source record"
        REVIEW = "review", "Needs identity/state review"
        UNSUPPORTED = "unsupported", "Estimation unsupported"
        FAILED = "failed", "Failed; retry scheduled"
        BLOCKED = "blocked", "Source access blocked; retry scheduled"

    structure = models.ForeignKey("Structure", on_delete=models.CASCADE, related_name="thermo_jobs")
    provider = models.CharField(max_length=24, choices=ThermoRecord.Provider.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    record = models.ForeignKey(ThermoRecord, null=True, blank=True, on_delete=models.SET_NULL)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("structure", "provider"), name="unique_structure_thermo_job")]
        indexes = [models.Index(fields=("provider", "status", "next_attempt_at"), name="thermo_job_due")]
        ordering = ("structure_id", "provider")


class ThermoProviderStatus(models.Model):
    provider = models.CharField(max_length=24, choices=ThermoRecord.Provider.choices, primary_key=True)
    retry_after = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Thermo(models.Model):
    source = models.ForeignKey("Source", null=True, on_delete=models.CASCADE)
    species = models.ForeignKey("Species", on_delete=models.CASCADE)
    prime_id = models.CharField(blank=True, max_length=11)
    preferred_key = models.CharField(blank=True, help_text="i.e. T 11/97, or J 3/65", max_length=20)
    reference_temp = models.FloatField(
        "Reference State Temperature", help_text="units: K", default=0.0
    )
    reference_pressure = models.FloatField(
        "Reference State Pressure", help_text="units: Pa", default=0.0
    )
    enthalpy_formation = models.FloatField(
        "Enthalpy of Formation", help_text="units: J/mol", null=True
    )
    coeffs_poly1 = ArrayField(models.FloatField(), verbose_name="Polynomial 1 Coefficients", size=7)
    coeffs_poly2 = ArrayField(models.FloatField(), verbose_name="Polynomial 2 Coefficients", size=7)
    temp_min_1 = models.FloatField("Polynomial 1 Lower Temp Bound", help_text="units: K")
    temp_max_1 = models.FloatField("Polynomial 1 Upper Temp Bound", help_text="units: K")
    temp_min_2 = models.FloatField("Polynomial 2 Lower Temp Bound", help_text="units: K")
    temp_max_2 = models.FloatField("Polynomial 2 Upper Temp Bound", help_text="units: K")

    class Meta:
        verbose_name_plural = "Thermodynamics"

    def heat_capacity(self, temp):
        "Heat capacity (J/mol/K) at specified temperature (K)"
        c1, c2, c3, c4, c5, _, _ = self._select_polynomial(temp)
        return (c1 + temp * (c2 + temp * (c3 + temp * (c4 + c5 * temp)))) * gas_constant

    def enthalpy(self, temp):
        "Enthalpy (J/mol) at specified temperature (K)"
        c1, c2, c3, c4, c5, c6, _ = self._select_polynomial(temp)
        temp2 = temp * temp
        return (
            c1 * temp
            + c2 * temp2 / 2.0
            + c3 * temp2 * temp / 3.0
            + c4 * temp2 * temp2 / 4.0
            + c5 * temp2 * temp2 * temp / 5.0
            + c6
        ) * gas_constant

    @property
    def enthalpy298(self):
        "Enthalpy (J/mol) at 298.15 K"
        return self.enthalpy(STANDARD_STATE_TEMPERATURE)

    def entropy(self, temp):
        "Entropy (J/mol/K) at specified temperature (K)"
        c1, c2, c3, c4, c5, _, c7 = self._select_polynomial(temp)
        temp2 = temp * temp
        return (
            c1 * log(temp)
            + c2 * temp
            + c3 * temp2 / 2.0
            + c4 * temp2 * temp / 3.0
            + c5 * temp2 * temp2 / 4.0
            + c7
        ) * gas_constant

    @property
    def entropy298(self):
        "Entropy (J/mol/K) at 298.15 K"
        return self.entropy(STANDARD_STATE_TEMPERATURE)

    def free_energy(self, temp, poly_num):
        "Gibbs Free Energy (J/mol) at specified temperature (K)"
        return self.enthalpy(temp) - temp * self.entropy(temp)

    def _select_polynomial(self, temperature):
        """
        Picks the appropriate polynomial for the specified temperature
        and returns the coefficients.
        """
        if temperature < self.temp_min_1:
            if (
                abs(temperature - STANDARD_STATE_TEMPERATURE) < 1e-9
                and self.temp_min_1 - temperature <= STANDARD_STATE_TEMPERATURE_TOLERANCE
            ):
                return self.coeffs_poly1
            raise ValueError(
                f"Requested temperature {temperature:.0f} K is below "
                f"minimum {self.temp_min_1:.0f} K"
            )
        elif temperature < self.temp_max_1:
            return self.coeffs_poly1
        elif temperature < self.temp_max_2:
            return self.coeffs_poly2
        else:
            raise ValueError(
                f"Requested temperature {temperature:.0f} K is above "
                f"maximum {self.temp_max_2:.0f} K"
            )

    def __str__(self):
        return (
            f"{self.id} "
            f"Species: {self.species.id} "
            f"H298: {self.enthalpy298:g} "
            f"S298: {self.entropy298:g}"
        )


class Transport(models.Model):
    """
    Some Transport data for a species
    """

    source = models.ForeignKey("Source", null=True, on_delete=models.CASCADE)
    species = models.ForeignKey("Species", on_delete=models.CASCADE)
    prime_id = models.CharField(blank=True, max_length=10)
    geometry = models.FloatField(blank=True, default=0.0)
    potential_well_depth = models.FloatField(
        "Potential Well Depth", blank=True, help_text="units: K", default=0.0
    )
    collision_diameter = models.FloatField(
        "Collision Diameter", blank=True, help_text="units: angstroms", default=0.0
    )
    dipole_moment = models.FloatField(blank=True, help_text="units: debye", default=0.0)
    polarizability = models.FloatField(blank=True, help_text="units: cubic angstroms", default=0.0)
    rotational_relaxation = models.FloatField("Rotational Relaxation", blank=True, default=0.0)

    def __str__(self):
        return f"{self.id} Species: {self.species} Source: {self.source.id}"
