"""Dataset species -> mechanism species names for a simulation (analysis.services.simulation).

The mechanism is exported from the database with names "label(index)". A standard InChI has
no spin, so two species of one model (O2 and singlet O2X) can share one; the matching never
chooses between them by the order of rows.
"""

from unittest import mock

from django.test import SimpleTestCase

from analysis.services import simulation
from analysis.services.simulation import _MechanismNames, _match_dataset_species


def no_aliases(db_label):
    return []


# H2-3 exports atomic oxygen as O(2), next to O2 and singlet O2X.
H2_3_LABELS = {"O": "[O]", "O2": "[O][O]", "O2X": "O=O", "N2": "N#N", "AR": "[Ar]"}
H2_3_NAMES = ["O(2)", "O2X(5)", "O2(10)", "N2(3)", "AR(1)"]


class MechanismNamesTests(SimpleTestCase):
    def test_the_export_index_is_not_part_of_the_name(self):
        names = _MechanismNames(["O(2)", "H(2)", "CO(2)", "CH(4)"])
        for label in ("O2", "H2", "CO2", "CH4"):
            self.assertIsNone(names.find(label), label)
        self.assertEqual(names.find("O"), "O(2)")
        self.assertEqual(names.find("CO"), "CO(2)")

    def test_case_and_punctuation(self):
        names = _MechanismNames(["AR(1)", "nC7H16(12)"])
        self.assertEqual(names.find("Ar"), "AR(1)")
        self.assertEqual(names.find("n-C7H16"), "nC7H16(12)")
        self.assertEqual(names.find("AR(1)"), "AR(1)")

    def test_a_label_that_names_several_species_names_none(self):
        names = _MechanismNames(["C3H2(S)(4)", "C3H2S(9)"])
        self.assertEqual(names.find("C3H2(S)"), "C3H2(S)(4)")
        self.assertIsNone(names.find("c3h2-s"))


class MatchDatasetSpeciesTests(SimpleTestCase):
    def match(self, dataset, labels=H2_3_LABELS, names=H2_3_NAMES, aliases=no_aliases):
        return dict(_match_dataset_species(dataset, labels, names, aliases))

    def test_o2_is_not_atomic_oxygen(self):
        keys = self.match({"O2": "O=O", "N2": "N#N", "Ar": "[Ar]"})
        self.assertEqual(keys, {"O2": "O2(10)", "N2": "N2(3)", "Ar": "AR(1)"})

    def test_species_sharing_an_inchi_are_not_chosen_by_row_order(self):
        for labels in (H2_3_LABELS, dict(reversed(list(H2_3_LABELS.items())))):
            self.assertEqual(self.match({"O2": "O=O"}, labels=labels), {"O2": "O2(10)"})
            self.assertEqual(self.match({"O2X": "O=O"}, labels=labels), {"O2X": "O2X(5)"})

    def test_a_name_that_names_neither_species_of_the_inchi_stays_unmapped(self):
        self.assertEqual(self.match({"oxygen": "O=O"}), {"oxygen": "oxygen"})

    def test_a_name_without_a_smiles_is_not_read_as_a_smiles(self):
        labels = {"CH3OH": "CO", "CO": "[C-]#[O+]", "H2O": "O", "O": "[O]"}
        names = ["O(2)", "CO(7)", "CH3OH(4)", "H2O(6)"]
        keys = self.match({"CO": "CO", "O": "O"}, labels=labels, names=names)
        self.assertEqual(keys, {"CO": "CO(7)", "O": "O(2)"})

    def test_matsugi_ch2_is_its_singlet(self):
        # PCI2013/269-Matsugi: CH2 is singlet methylene and HCH the triplet, as its file says.
        labels = {"HCH": "[CH2]", "CH2": "[CH2]"}
        keys = self.match({"CH2": "[CH2]", "HCH": "[CH2]"}, labels=labels, names=["HCH(1)", "CH2(2)"])
        self.assertEqual(keys, {"CH2": "CH2(2)", "HCH": "HCH(1)"})

    def test_a_unique_inchi_maps_whatever_the_names(self):
        keys = self.match({"2-butanol": "CCC(C)O"}, labels={"sc4h9oh": "CCC(C)O"}, names=["sc4h9oh(55)"])
        self.assertEqual(keys, {"2-butanol": "sc4h9oh(55)"})

    def test_a_db_label_reaches_its_mechanism_name_through_its_record(self):
        aliases = {"sc4h9oh": ["sc4h9oh", "N2C4H9OH"]}.get
        keys = self.match({"2-butanol": "CCC(C)O"}, labels={"sc4h9oh": "CCC(C)O"},
                          names=["N2C4H9OH(55)"], aliases=lambda label: aliases(label, []))
        self.assertEqual(keys, {"2-butanol": "N2C4H9OH(55)"})


class BuildSpecKeysTests(SimpleTestCase):
    def test_the_dataset_and_model_species_are_matched(self):
        with mock.patch.object(simulation, "get_species_label_smiles_map", return_value=H2_3_LABELS), \
                mock.patch.object(simulation, "get_dataset_species_map", return_value={"O2": "O=O", "N2": "N#N"}):
            keys = simulation.build_spec_keys_for_dataset(object(), object(), H2_3_NAMES)
        self.assertEqual(dict(keys), {"O2": "O2(10)", "N2": "N2(3)"})
