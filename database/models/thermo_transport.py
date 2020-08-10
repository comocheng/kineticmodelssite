from math import log

from django.db import models
from django.contrib.postgres.fields import ArrayField
from rmgpy.constants import R as gas_constant


class Thermo(models.Model):
    """
    A thermochemistry polynomial set

    What Kinetics is to Reaction, Thermo is to Species.

    This is the equivalent of the 'th' data within 'Species/data' in PrIMe,
    which contain:
    *****in data******* (usually has thp prime ID (shown below), but sometimes
        near end of list has completely different xml type under a ca prime ID)
    Preferred Key (in thermo file, group="prime": What does this mean?)
                    (i.e. ATcT /A, RUS 79)
    Tref (units K)
    Pref (units Pa)
    dfH (units J/mol)
    Polynomial 1:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
    Polynomial 2:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
    """

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
    coeffs_poly1 = ArrayField(models.FloatField(), size=7)
    coeffs_poly2 = ArrayField(models.FloatField(), size=7)
    temp_min_1 = models.FloatField("Polynomial 1 Lower Temp Bound", help_text="units: K")
    temp_max_1 = models.FloatField("Polynomial 1 Upper Temp Bound", help_text="units: K")
    temp_min_2 = models.FloatField("Polynomial 2 Lower Temp Bound", help_text="units: K")
    temp_max_2 = models.FloatField("Polynomial 2 Upper Temp Bound", help_text="units: K")

    def heat_capacity(self, temp, poly_num):
        c1, c2, c3, c4, c5, _, _ = self._polynomial_select(
            poly_num, self.coeffs_poly1, self.coeffs_poly2
        )
        return (c1 + temp * (c2 + temp * (c3 + temp * (c4 + c5 * temp)))) * gas_constant

    def enthalpy(self, temp, poly_num):
        c1, c2, c3, c4, c5, c6, _ = self._polynomial_select(
            poly_num, self.coeffs_poly1, self.coeffs_poly2
        )
        return (
            (
                c1
                + c2 * temp / 2.0
                + c3 * temp ** 2 / 3.0
                + c4 * temp ** 2 * temp / 4.0
                + c5 * temp ** 4 / 5.0
                + c6 / temp
            )
            * gas_constant
            * temp
        )

    def entropy(self, temp, poly_num):
        c1, c2, c3, c4, c5, _, c7 = self._polynomial_select(
            poly_num, self.coeffs_poly1, self.coeffs_poly2
        )
        return (
            c1 * log(temp)
            + c2 * temp
            + c3 * temp ** 2 / 2.0
            + c4 * temp ** 2 * temp / 3.0
            + c5 * temp ** 4 / 4.0
            + c7
        ) * gas_constant

    def free_energy(self, temp, poly_num):
        return self.enthalpy(temp, poly_num) - temp * self.entropy(temp, poly_num)

    def temp_range(self, poly_num, temp_step):
        temp_min, temp_max = self._polynomial_select(
            poly_num, (self.temp_min_1, self.temp_max_1), (self.temp_min_2, self.temp_max_2)
        )
        return range(temp_min, temp_max + 1, temp_step)

    def heat_capacities(self, poly_num, temp_step):
        return self._get_properties_over_temp_range(self.heat_capacity, poly_num, temp_step)

    def enthalpies(self, poly_num, temp_step):
        return self._get_properties_over_temp_range(self.enthalpy, poly_num, temp_step)

    def entropies(self, poly_num, temp_step):
        return self._get_properties_over_temp_range(self.entropy, poly_num, temp_step)

    def free_energies(self, poly_num, temp_step):
        return self._get_properties_over_temp_range(self.free_energy, poly_num, temp_step)

    def _polynomial_select(poly_num, result_poly1, result_poly2):
        if poly_num == 1:
            return result_poly1
        elif poly_num == 2:
            return result_poly2
        else:
            raise ValueError("polynomial number invalid, pick '1' or '2'")

    def _get_properties_over_temp_range(self, property_func, poly_num, temp_step):
        return [property_func(temp, poly_num) for temp in self.temp_range(poly_num, temp_step)]


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
        return f"{super().__str__()} | Species: {self.species}"
