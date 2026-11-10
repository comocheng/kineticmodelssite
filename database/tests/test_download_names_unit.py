"""The downloads write each species under the model's name, without RMG-Py's index. AramcoMech 1.3's
CH2CHOOHCOCH3 was written C4H7O3(29): RMG-Py writes label(index) only when that has 16 characters or
fewer, and else the formula. A name CHEMKIN cannot take keeps RMG-Py's index, and so does a name that
another species is written as. A species named NO stays NO when a simulation adds an inert species to
the Cantera file (PyYAML reads NO as False)."""
import os
import shutil
import tempfile

from django.test import SimpleTestCase


def rmg_species(index, label, smiles):
    from rmgpy.molecule import Molecule
    from rmgpy.species import Species

    return Species(index=index, label=label, molecule=[Molecule(smiles=smiles)])


class WriteModelNamesTests(SimpleTestCase):

    def written(self, *entries):
        """The names RMG-Py writes for species (index, label, SMILES) after _write_model_names, and
        what it returns."""
        from rmgpy.chemkin import get_species_identifier
        from database.services import exports

        species = [rmg_species(*entry) for entry in entries]
        kept = exports._write_model_names(species)
        self.assertEqual([s.index for s in species], [-1] * len(species))
        return [get_species_identifier(s) for s in species], kept

    def test_the_models_name_without_the_index(self):
        names, kept = self.written((29, "CH2CHOOHCOCH3", "[CH2]C(OO)C(C)=O"), (1, "OH", "[OH]"),
                                   (2, "C6H5CH2COCH2O2H", "OOCC(=O)Cc1ccccc1"))
        self.assertEqual(names, ["CH2CHOOHCOCH3", "OH", "C6H5CH2COCH2O2H"])
        self.assertEqual(kept, [])

    def test_a_name_chemkin_cannot_take_keeps_the_index(self):
        names, kept = self.written((5, "[CH2]C=O", "[CH2]C=O"), (6, "C4H8OOH1-3O2ABCD", "CC(OO)CCO[O]"),
                                   (7, "C4H8OOH1-3O2ABCDE", "CC(OO)CCO[O]"))
        # 16 characters is CHEMKIN's limit; a SMILES has characters RMG-Py does not write.
        self.assertEqual(names, ["C2H3O(5)", "C4H8OOH1-3O2ABCD", "C4H9O4(7)"])
        self.assertEqual(kept, [("[CH2]C=O", "C2H3O(5)"), ("C4H8OOH1-3O2ABCDE", "C4H9O4(7)")])

    def test_a_name_another_species_is_written_as_keeps_the_index(self):
        # A model's own name with digits in brackets, as Allen's OH(19), against RMG-Py's name for a
        # species with a SMILES name.
        names, kept = self.written((1, "C2H3O(5)", "C=C[O]"), (5, "[CH2]C=O", "[CH2]C=O"))
        self.assertEqual(names, ["C2H3O(5)(1)", "C2H3O(5)"])
        self.assertEqual(kept, [("C2H3O(5)", "C2H3O(5)(1)"), ("[CH2]C=O", "C2H3O(5)")])

    def test_the_header_names_the_species_that_keep_the_index(self):
        from database.services import exports

        self.assertEqual(exports._kept_index_header([]), b"")
        header = exports._kept_index_header([("[CH2]C=O", "C2H3O(5)")]).decode()
        self.assertTrue(header.startswith("! Prometheus writes 1 species of this model with RMG-Py's index"))
        self.assertTrue(header.endswith("! [CH2]C=O as C2H3O(5)\n"))
        self.assertTrue(all(line.startswith("!") for line in header.splitlines()))


def plain(value):
    """Cantera's input data as plain dicts and lists, for yaml.safe_dump."""
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


class InertInjectionTests(SimpleTestCase):

    def test_a_species_named_no_stays_no(self):
        import cantera as ct
        import yaml
        from analysis.services.simulation import _inject_inert_species

        gri = ct.Solution("gri30.yaml")
        names = ["O", "O2", "N", "NO", "N2"]
        mechanism = {
            "units": {"length": "cm", "time": "s", "quantity": "mol", "activation-energy": "cal/mol"},
            # Ar is an element of the phase, so the injected Ar species can be added.
            "phases": [{"name": "gas", "thermo": "ideal-gas", "elements": ["O", "N", "Ar"], "species": names,
                        "kinetics": "gas", "reactions": "all", "state": {"T": 300.0, "P": "1 atm"}}],
            "species": [plain(gri.species(name).input_data) for name in names],
            "reactions": [{"equation": "N + NO <=> N2 + O", "rate-constant": {"A": 2.7e13, "b": 0.0, "Ea": 355.0}},
                          {"equation": "N + O2 <=> NO + O", "rate-constant": {"A": 9.0e9, "b": 1.0, "Ea": 6500.0}}],
        }
        # As ck2yaml writes it: NO without quotes.
        text = yaml.safe_dump(mechanism, sort_keys=False).replace("'NO'", "NO")
        self.assertIn("name: NO\n", text)
        directory = tempfile.mkdtemp()
        try:
            path = os.path.join(directory, "mechanism.yaml")
            with open(path, "w") as handle:
                handle.write(text)
            self.assertEqual(ct.Solution(path).n_species, 5)
            gas = ct.Solution(_inject_inert_species(path, ["AR"]))
            self.assertEqual(gas.species_names, [*names, "Ar"])
            self.assertEqual([r.equation for r in gas.reactions()], ["N + NO <=> N2 + O", "N + O2 <=> NO + O"])
        finally:
            shutil.rmtree(directory)
