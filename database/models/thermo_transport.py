from math import log

from django.db import models
from django.contrib.postgres.fields import ArrayField
from rmgpy.constants import R as gas_constant


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
        return self.enthalpy(298.15)

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
        return self.entropy(298.15)

    def free_energy(self, temp, poly_num):
        "Gibbs Free Energy (J/mol) at specified temperature (K)"
        return self.enthalpy(temp) - temp * self.entropy(temp)

    def _select_polynomial(self, temperature):
        """
        Picks the appropriate polynomial for the specified temperature
        and returns the coefficients.
        """
        if temperature < self.temp_min_1:
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
        return f"{self.id} Species: {self.species.id} H298: {self.enthalpy298:g} S298: {self.entropy298:g}"


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
