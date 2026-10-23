import math

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rmgpy import kinetics as rmg_kinetics
from rmgpy.molecule import Molecule

from database import models
from database.scripts.import_rmg_models import create_kinetics_data, get_base_kinetics_data_fields
from database.services import curves
from database.services.chemical_identity import rate_fingerprint
from database.services import thermo_sources as sources
from database.tests.test_thermo_sources_unit import nasa_fixture


def arrhenius(A, n, E):
    return rmg_kinetics.Arrhenius(A=(A, "cm^3/(mol*s)"), n=n, Ea=(E, "kcal/mol"), T0=(1, "K"))


class CurveTests(TestCase):
    def setUp(self):
        self.species = sources._species_and_structure(Molecule().from_smiles("C"), "Methane")[0]

    def thermo(self, *model_names):
        thermo = models.Thermo.objects.create(species=self.species, reference_temp=298.15,
                                              **sources.nasa_fields(nasa_fixture()))
        for name in model_names:
            model, _ = models.KineticModel.objects.get_or_create(model_name=name)
            models.ThermoComment.objects.create(thermo=thermo, kinetic_model=model)
        return thermo

    def test_thermo_curve_matches_polynomial_and_stays_inside_its_range(self):
        thermo = self.thermo("A")
        curve = curves.thermo_curve(thermo)
        # Every point evaluates, up to (just inside) the top bound, where Thermo itself raises.
        self.assertEqual(len(curve["T"]), curves.THERMO_POINTS)
        self.assertAlmostEqual(curve["T"][-1], thermo.temp_max_2, places=1)
        index = min(range(len(curve["T"])), key=lambda i: abs(curve["T"][i] - 1500))
        self.assertAlmostEqual(curve["Cp"][index], thermo.heat_capacity(curve["T"][index]), delta=1e-3)
        self.assertAlmostEqual(curve["H"][index], thermo.enthalpy(curve["T"][index]) / 1000, delta=1e-3)

    def test_identical_polynomials_from_several_models_plot_once(self):
        self.thermo("Model A")
        self.thermo("Model B")
        plot = curves.species_thermo_plot(models.Thermo.objects.filter(species=self.species)
                                          .prefetch_related("thermocomment_set__kinetic_model"), [])
        self.assertEqual(len(plot["curves"]), 1)
        self.assertEqual(plot["curves"][0]["models"], ["Model A", "Model B"])
        self.assertEqual(plot["curves"][0]["label"], "Model A +1")
        page = self.client.get(reverse("species-detail", args=[self.species.pk]))
        self.assertContains(page, 'id="thermo-plot-data"')
        self.assertContains(page, "database/plots.js")

    def reaction(self):
        h, o2, oh, o = (sources._species_and_structure(Molecule().from_smiles(s), s)[0] for s in ("[H]", "[O][O]", "[OH]", "[O]"))
        reaction = models.Reaction.objects.create(hash="h+o2", reversible=True)
        for species, coeff in ((h, -1), (o2, -1), (oh, 1), (o, 1)):
            models.Stoichiometry.objects.create(reaction=reaction, species=species, coeff=coeff)
        return reaction

    def test_rate_curve_is_in_cm3_units_and_matches_rmg(self):
        reaction = self.reaction()
        rmg = arrhenius(1e14, 0, 16)
        kinetics = models.Kinetics.objects.create(reaction=reaction, raw_data=create_kinetics_data(None, rmg, None))
        curve = curves.rate_curve(kinetics, curves.reaction_order(reaction))
        self.assertEqual(curves.reaction_order(reaction), 2)
        T = curve["T"][10]
        self.assertAlmostEqual(math.log10(curve["k"]["1.0"][10]), math.log10(rmg.get_rate_coefficient(T) * 1e6), places=3)
        page = self.client.get(reverse("reaction-detail", args=[reaction.pk]))
        self.assertContains(page, 'id="rate-plot-data"')

    def test_plog_curves_follow_pressure(self):
        reaction = self.reaction()
        plog = rmg_kinetics.PDepArrhenius(pressures=([0.1, 10], "atm"), arrhenius=[arrhenius(1e12, 0, 10), arrhenius(1e14, 0, 10)],
                                          Tmin=(300, "K"), Tmax=(2000, "K"), Pmin=(0.1, "atm"), Pmax=(10, "atm"))
        kinetics = models.Kinetics.objects.create(reaction=reaction, raw_data=create_kinetics_data(None, plog, None),
                                                  **get_base_kinetics_data_fields(plog))
        curve = curves.rate_curve(kinetics, 2)
        self.assertTrue(curve["pdep"])
        # Only pressures inside the fit's range are offered.
        self.assertEqual(curve["pressures"], [0.1, 1.0, 10.0])
        self.assertLess(curve["k"]["0.1"][0], curve["k"]["10.0"][0])
        self.assertEqual(curve["valid_range"], [300.0, 2000.0])


class EnthalpyDependentRateTests(SimpleTestCase):
    def test_evans_polanyi_rates_are_not_evaluated_at_a_pressure(self):
        # get_rate_coefficient's second argument is the reaction enthalpy for these, not pressure.
        rate = rmg_kinetics.ArrheniusEP(A=(1e5, "cm^3/(mol*s)"), n=0, alpha=0.5, E0=(10, "kcal/mol"))
        self.assertIsNone(rate_fingerprint(rate))
        record = models.KineticsRecord(raw_data=create_kinetics_data(None, rate, None))
        self.assertIsNone(curves.rate_curve(record, 2))
