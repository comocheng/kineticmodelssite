import math

import numpy as np
from django.test import SimpleTestCase, TestCase
from rmgpy import kinetics as rmg_kinetics
from rmgpy.molecule import Molecule

from database import models
from database.models import kinetic_data as kd
from database.scripts.import_rmg_models import create_kinetics_data, get_base_kinetics_data_fields
from database.services import chemistry_index
from database.services import thermo_sources as sources
from database.services.chemical_identity import reaction_key, reaction_layer, rates_match, structure_key


def arrhenius(A, n, E):
    return rmg_kinetics.Arrhenius(A=(A, "cm^3/(mol*s)"), n=n, Ea=(E, "kcal/mol"), T0=(1, "K"))


class PressureDependentConverterTests(SimpleTestCase):
    def assert_round_trip(self, rmg):
        data = create_kinetics_data(None, rmg, None)
        base = get_base_kinetics_data_fields(rmg)
        back = kd.validate_kinetics_data(data, returns=True).to_rmg(
            base.get("min_temp"), base.get("max_temp"), base.get("min_pressure"), base.get("max_pressure"), [])
        for T in (500, 1000, 1500):
            for P in (2e4, 1e5, 5e5):
                self.assertAlmostEqual(math.log10(back.get_rate_coefficient(T, P)),
                                       math.log10(rmg.get_rate_coefficient(T, P)), places=9)
        return kd.validate_kinetics_data(data, returns=True)

    def test_plog_with_duplicate_lines_at_one_pressure(self):
        plog = rmg_kinetics.PDepArrhenius(pressures=([0.1, 1, 10], "atm"), arrhenius=[
            arrhenius(1e12, 0.5, 10),
            rmg_kinetics.MultiArrhenius(arrhenius=[arrhenius(1e11, 0.3, 8), arrhenius(2e12, 0, 12)]),
            arrhenius(3e13, -0.2, 11)])
        stored = self.assert_round_trip(plog)
        self.assertEqual(len(stored.table_data()[0][2]), 4)

    def test_multi_plog(self):
        plog = rmg_kinetics.PDepArrhenius(pressures=([0.1, 10], "atm"), arrhenius=[arrhenius(1e12, 0.5, 10), arrhenius(3e13, 0, 11)])
        other = rmg_kinetics.PDepArrhenius(pressures=([0.1, 10], "atm"), arrhenius=[arrhenius(1e10, 1, 5), arrhenius(2e10, 1, 5)])
        self.assert_round_trip(rmg_kinetics.MultiPDepArrhenius(arrhenius=[plog, other]))

    def test_chebyshev_keeps_coefficients_in_their_units(self):
        coeffs = np.array([[11.6, 0.6, -0.3], [-0.5, 0.4, 0.1]])
        cheb = rmg_kinetics.Chebyshev(coeffs=coeffs.copy(), kunits="cm^3/(mol*s)", Tmin=(300, "K"), Tmax=(2500, "K"),
                                      Pmin=(0.01, "atm"), Pmax=(100, "atm"))
        stored = self.assert_round_trip(cheb)
        # Stored as written in the library, not with RMG's SI factor folded into [0][0].
        self.assertAlmostEqual(stored.coefficient_matrix[0][0], 11.6)
        self.assertEqual(len(stored.table_data()[0][2]), 2)


class IdentityRuleTests(SimpleTestCase):
    def test_reverse_reactions_share_a_key(self):
        forward = reaction_key(["H-2", "O2-3"], ["OH-2", "O-3"])
        reverse = reaction_key(["O-3", "OH-2"], ["O2-3", "H-2"])
        self.assertEqual(forward[0], reverse[0])
        self.assertEqual({forward[1], reverse[1]}, {1, -1})
        self.assertEqual(reaction_key(["A"], [""]), ("", 0))

    def test_spin_states_have_different_keys(self):
        triplet = Molecule().from_adjacency_list("multiplicity 3\n1 C u2 p0 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}")
        singlet = Molecule().from_adjacency_list("1 C u0 p1 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}")
        self.assertNotEqual(structure_key(triplet), structure_key(singlet))
        allyl = [Molecule().from_smiles(smiles) for smiles in ("[CH2]C=C", "C=C[CH2]")]
        self.assertEqual(structure_key(allyl[0]), structure_key(allyl[1]))

    def test_layers(self):
        for formulas, layer in [(["H2", "O2", "HO2"], "H2/O2"), (["CH4", "OH"], "C1"), (["C2H6", "H"], "C2"),
                                (["C5H12", "OH"], "C≥4"), (["NO", "HO2"], "N"), (["CH3", "NO2"], "C1+N"),
                                (["CF3Br", "H"], "C1+Hal"), (["SO2", "O"], "S"), (["H2", "Ar"], "H2/O2")]:
            with self.subTest(formulas=formulas):
                self.assertEqual(reaction_layer(formulas), layer)

    def test_rate_tolerance(self):
        self.assertTrue(rates_match([1.0, 2.0, 3.0], [1.005, 2.0, 2.995]))
        self.assertFalse(rates_match([1.0, 2.0, 3.0], [1.02, 2.0, 3.0]))
        self.assertFalse(rates_match([], [1.0, 2.0, 3.0]))


class ReactionIndexTests(TestCase):
    def species(self, smiles):
        return sources._species_and_structure(Molecule().from_smiles(smiles), smiles)[0]

    def reaction(self, reactants, products, hash_):
        from collections import Counter
        reaction = models.Reaction.objects.create(hash=hash_, reversible=True)
        for side, sign in ((reactants, -1), (products, 1)):
            for species, count in Counter(side).items():
                models.Stoichiometry.objects.create(reaction=reaction, species=species, coeff=sign * count)
        return reaction

    def test_reverse_duplicates_share_a_key_and_colliders_do_not_set_the_layer(self):
        h, o2, oh, o, ar = (self.species(s) for s in ("[H]", "[O][O]", "[OH]", "[O]", "[Ar]"))
        forward = self.reaction([h, o2], [oh, o], "f")
        reverse = self.reaction([oh, o], [h, o2], "r")
        chemistry_index.index_reactions()
        forward.refresh_from_db()
        reverse.refresh_from_db()
        self.assertTrue(forward.canonical_key)
        self.assertEqual(forward.canonical_key, reverse.canonical_key)
        self.assertEqual(forward.canonical_direction, -reverse.canonical_direction)
        self.assertEqual(forward.layer, "H2/O2")
        h2 = self.species("[H][H]")
        collider = self.reaction([h2, ar], [h, h, ar], "c")
        chemistry_index.index_reaction(collider)
        self.assertEqual(collider.layer, "H2/O2")
        self.assertEqual(collider.canonical_key.count("+"), 3)

    def test_fingerprint_matches_rmg(self):
        h, o2, oh, o = (self.species(s) for s in ("[H]", "[O][O]", "[OH]", "[O]"))
        reaction = self.reaction([h, o2], [oh, o], "k")
        data = create_kinetics_data(None, arrhenius(1e14, 0, 16), None)
        kinetics = models.Kinetics.objects.create(reaction=reaction, raw_data=data)
        chemistry_index.index_kinetics()
        kinetics.refresh_from_db()
        expected = [round(math.log10(arrhenius(1e14, 0, 16).get_rate_coefficient(T, 1e5)), 4) for T in (500, 1000, 1500)]
        self.assertEqual(kinetics.rate_fingerprint, expected)
        broken = models.Kinetics.objects.create(reaction=reaction, raw_data={"type": "kinetics_data", "temps": [300], "rate_coeffs": [1]})
        chemistry_index.index_kinetics()
        broken.refresh_from_db()
        self.assertEqual(broken.rate_fingerprint, [])
