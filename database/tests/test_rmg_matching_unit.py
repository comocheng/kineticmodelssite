import tempfile
from collections import Counter
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rmgpy import kinetics as rmg_kinetics
from rmgpy.molecule import Molecule

from database import models
from database.scripts.import_rmg_models import create_kinetics_data
from database.scripts.rmg_libraries import rejection
from database.services import chemistry_index, rmg_matching
from database.services import thermo_sources as sources

LIBRARY = '''name = "Test"
shortDesc = ""
longDesc = """Fixture."""
entry(
    index = 1,
    label = "H + O2 <=> OH + O",
    kinetics = Arrhenius(A=(1e14, 'cm^3/(mol*s)'), n=0, Ea=(16, 'kcal/mol'), T0=(1, 'K')),
)
entry(
    index = 2,
    label = "C2H2 + O2 <=> H + H + CO + CO",
    kinetics = Arrhenius(A=(1e10, 'cm^3/(mol*s)'), n=0, Ea=(10, 'kcal/mol'), T0=(1, 'K')),
)
entry(
    index = 3,
    label = "H + CO <=> HCO",
    kinetics = Arrhenius(A=(1e12, 'cm^3/(mol*s)'), n=0, Ea=(2, 'kcal/mol'), T0=(1, 'K')),
)
'''
SPECIES = {"H": "[H]", "O2": "[O][O]", "OH": "[OH]", "O": "[O]", "C2H2": "C#C", "CO": "[C-]#[O+]", "HCO": "[CH]=O"}


def write_library(directory):
    (Path(directory) / "reactions.py").write_text(LIBRARY)
    blocks = []
    for label, smiles in SPECIES.items():
        molecule = Molecule().from_smiles(smiles)
        blocks.append(f"{label}\n{molecule.to_adjacency_list()}")
    (Path(directory) / "dictionary.txt").write_text("\n".join(blocks) + "\n")
    return Path(directory) / "reactions.py"


class RejectionTests(SimpleTestCase):
    def test_only_reactions_rmg4_refuses_are_skipped(self):
        labels = {"H", "O2", "OH", "O", "AR"}
        self.assertIsNone(rejection("H + O2 <=> OH + O", labels))
        self.assertEqual(rejection("A + B => C + D + E + F", {"A", "B", "C", "D", "E", "F"}), "more than 3 reactants or products")
        self.assertIn("collider HE", rejection("H + O2 (+HE) <=> HO2 (+HE)", labels | {"HO2"}))
        self.assertIsNone(rejection("H + O2 (+M) <=> HO2 (+M)", labels | {"HO2"}))
        self.assertIsNone(rejection("H + O2 (+AR) <=> HO2 (+AR)", labels | {"HO2"}))


class LibraryMatchingTests(TestCase):
    def species(self, smiles):
        return sources._species_and_structure(Molecule().from_smiles(smiles), smiles)[0]

    def reaction(self, reactants, products, hash_):
        reaction = models.Reaction.objects.create(hash=hash_, reversible=True)
        for side, sign in ((reactants, -1), (products, 1)):
            for species, count in Counter(side).items():
                models.Stoichiometry.objects.create(reaction=reaction, species=species, coeff=sign * count)
        return reaction

    def test_library_rates_attach_compare_and_summarize(self):
        h, o2, oh, o = (self.species(SPECIES[name]) for name in ("H", "O2", "OH", "O"))
        forward = self.reaction([h, o2], [oh, o], "forward")
        backward = self.reaction([oh, o], [h, o2], "backward")
        rate = rmg_kinetics.Arrhenius(A=(1e14, "cm^3/(mol*s)"), n=0, Ea=(16, "kcal/mol"), T0=(1, "K"))
        kinetics = models.Kinetics.objects.create(reaction=forward, raw_data=create_kinetics_data(None, rate, None))
        model = models.KineticModel.objects.create(model_name="Copied model")
        models.KineticsComment.objects.create(kinetics=kinetics, kinetic_model=model, comment="")
        chemistry_index.index_reactions()
        chemistry_index.index_kinetics()
        with tempfile.TemporaryDirectory() as directory:
            stats = rmg_matching.match_kinetics_library("Test", write_library(directory), "test-version",
                                                        rmg_matching.site_reaction_index())
        # The four-product reaction is skipped, not the whole library; HCO is not on the site.
        self.assertEqual((stats["rejected"], stats["matched"]), (1, 1))
        record = models.KineticsRecord.objects.get()
        forward.refresh_from_db()
        self.assertEqual(record.reaction, forward)
        self.assertEqual(record.canonical_direction, forward.canonical_direction)
        self.assertEqual(rmg_matching.kinetics_overlaps("test-version"), 1)
        overlap = models.ModelLibraryOverlap.objects.get()
        self.assertEqual((overlap.library, overlap.model_total, overlap.shared, overlap.identical), ("Test", 1, 1, 1))
        page = self.client.get(reverse("reaction-detail", args=[forward.pk]))
        self.assertContains(page, "RMG-database counterparts")
        self.assertContains(page, "Copied model")
        library_url = reverse("rmg-library-detail", args=["kinetics", "Test"])
        self.assertContains(page, f'href="{library_url}"')
        self.assertContains(page, f'href="{reverse("kinetic-model-detail", args=[model.pk])}"')
        self.assertContains(page, "https://rmg.mit.edu/database/kinetics/libraries/Test/1/")
        # Seen from the reverse-written row, the same record reads backwards.
        self.assertContains(self.client.get(reverse("reaction-detail", args=[backward.pk])), "reverse (not plotted)")
        self.assertContains(self.client.get(reverse("kinetic-model-detail", args=[model.pk])), "1 of 1 (100%)")

        # The library, its family and its models all have pages.
        library = self.client.get(library_url)
        self.assertContains(library, "Copied model")
        self.assertContains(library, reverse("reaction-detail", args=[forward.pk]))
        self.assertContains(library, "https://rmg.mit.edu/database/kinetics/libraries/Test/")
        self.assertContains(self.client.get(reverse("rmg-library-list")), library_url)
        self.assertContains(self.client.get(reverse("kinetic-model-detail", args=[model.pk])), library_url)
        self.assertEqual(self.client.get(reverse("rmg-library-detail", args=["kinetics", "Missing"])).status_code, 404)
        models.Reaction.objects.filter(pk__in=[forward.pk, backward.pk]).update(rmg_family="H_Abstraction")
        family_url = reverse("rmg-family-detail", args=["H_Abstraction"])
        self.assertContains(self.client.get(reverse("rmg-family-list")), family_url)
        family = self.client.get(family_url)
        self.assertContains(family, "1 reactions on this site")   # the two rows are one reaction
        self.assertContains(family, "https://rmg.mit.edu/database/kinetics/families/H_Abstraction/")
        self.assertContains(self.client.get(reverse("reaction-detail", args=[forward.pk])), family_url)
        self.assertEqual(self.client.get(reverse("rmg-family-detail", args=["Missing"])).status_code, 404)
