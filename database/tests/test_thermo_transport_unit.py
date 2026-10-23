from django.test import SimpleTestCase

from database.models.thermo_transport import Thermo


class ThermoPolynomialSelectionTests(SimpleTestCase):
    def make_thermo(self, temp_min_1=300.0):
        return Thermo(
            coeffs_poly1=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            coeffs_poly2=[2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            temp_min_1=temp_min_1,
            temp_max_1=1000.0,
            temp_min_2=1000.0,
            temp_max_2=5000.0,
        )

    def test_enthalpy298_allows_common_300_k_lower_bound(self):
        thermo = self.make_thermo(temp_min_1=300.0)

        self.assertIsInstance(thermo.enthalpy298, float)

    def test_temperatures_below_300_k_still_raise_outside_standard_state(self):
        thermo = self.make_thermo(temp_min_1=300.0)

        with self.assertRaisesRegex(ValueError, "below minimum 300 K"):
            thermo.enthalpy(297.0)

    def test_enthalpy298_still_raises_when_lower_bound_is_not_near_298_k(self):
        thermo = self.make_thermo(temp_min_1=400.0)

        with self.assertRaisesRegex(ValueError, "below minimum 400 K"):
            thermo.enthalpy298
