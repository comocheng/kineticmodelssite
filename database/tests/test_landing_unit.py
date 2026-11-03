import re
import string

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from database.models import Formula, Isomer, KineticModel, Source, Species, SpeciesName, Structure
from database.services import landing

PROPYNE = "InChI=1S/C3H4/c1-3-2/h1H,2H3"
ALLENE = "InChI=1S/C3H4/c1-3-2/h1-2H2"


def strings(value):
    """Every string in the copy, except identifiers that are not prose."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in {"url", "href", "style", "key", "inchi", "condensed", "shared_name"}:
                yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


class LandingCopyTests(SimpleTestCase):
    """The copy file is edited by hand, so check what an edit can break."""

    def setUp(self):
        self.copy = landing.load_copy()

    def test_each_placeholder_is_a_live_number(self):
        keys = set(landing.LIVE_KEYS) | {
            f"{entry['key']}_{suffix}"
            for entry in self.copy["problem"]["species"] for suffix in landing.SCENE_KEY_SUFFIXES
        }
        used = {field for text in strings(self.copy)
                for _, field, _, _ in string.Formatter().parse(text) if field}
        self.assertEqual(used - keys, set())

    def test_each_url_name_resolves(self):
        def urls(value):
            if isinstance(value, dict):
                if "url" in value:
                    yield value["url"]
                for item in value.values():
                    yield from urls(item)
            elif isinstance(value, list):
                for item in value:
                    yield from urls(item)

        names = list(urls(self.copy))
        self.assertTrue(names)
        for name in names:
            with self.subTest(url=name):
                reverse(name)

    def test_sentences_follow_the_ste_length_limit(self):
        for text in strings(self.copy):
            for sentence in re.split(r"(?<=[.?!])\s+", text):
                with self.subTest(sentence=sentence):
                    self.assertLessEqual(len(sentence.split()), 25)

    def test_fill_keeps_an_unknown_key_visible(self):
        filled = landing.fill({"a": ["{models} models, {nope}"]}, {"models": "100"})
        self.assertEqual(filled, {"a": ["100 models, {nope}"]})

    def test_citation_comes_from_citation_cff(self):
        citation = landing.citation()
        self.assertEqual(citation["authors"], "Lekia, P.; West, R. H.; Niemeyer, K. E.")
        self.assertEqual(citation["title"], "Pr.omethe.us Kinetic Models Database")
        self.assertEqual(citation["url"], "https://pr.omethe.us")


class LandingSceneTests(TestCase):
    @classmethod
    def add_molecule(cls, label, inchi, smiles):
        formula, _ = Formula.objects.get_or_create(formula="C3H4")
        isomer = Isomer.objects.create(formula=formula, inchi=inchi)
        Structure.objects.create(isomer=isomer, smiles=smiles, adjacency_list=f"fixture {label}", multiplicity=1)
        species = Species.objects.create(hash=label)
        species.isomers.add(isomer)
        return species

    @classmethod
    def setUpTestData(cls):
        source = Source.objects.create()
        model_a = KineticModel.objects.create(model_name="A", source=source)
        model_b = KineticModel.objects.create(model_name="B", source=source)
        propyne = cls.add_molecule("propyne", PROPYNE, "C#CC")
        # A model's second name for one structure is its own species record
        propyne_variant = Species.objects.create(hash="propyne-variant", variant="B: CC#C")
        propyne_variant.isomers.add(propyne.isomers.get())
        allene = cls.add_molecule("allene", ALLENE, "C=C=C")
        SpeciesName.objects.create(species=propyne, kinetic_model=model_a, name="C3H4-P")
        SpeciesName.objects.create(species=propyne, kinetic_model=model_b, name="PC3H4")
        SpeciesName.objects.create(species=propyne_variant, kinetic_model=model_b, name="CC#C")
        SpeciesName.objects.create(species=propyne, name="Propyne")
        SpeciesName.objects.create(species=allene, kinetic_model=model_a, name="C3H4")

    def setUp(self):
        cache.clear()

    def test_names_count_every_species_of_the_inchi(self):
        molecule = landing.scene_molecule({"key": "propyne", "inchi": PROPYNE})
        self.assertEqual([row["name"] for row in molecule["names"]], ["C3H4-P", "CC#C", "PC3H4"])
        self.assertEqual(molecule["models"], 2)
        self.assertEqual(molecule["smiles"], "C#CC")

    def test_flame_species_are_the_most_used_under_their_most_common_name(self):
        # Propyne is in both models; the tie between its two names goes to the first in order
        # C3H4-P and C3H4 spell the atoms of C3H4, so their digits are subscripts; CC#C is SMILES
        self.assertEqual(landing.flame_species(), [
            {"name": "C3H4-P", "models": 2, "subscripts": True},
            {"name": "CC#C", "models": 1, "subscripts": False},
            {"name": "C3H4", "models": 1, "subscripts": True},
        ])
        self.assertEqual(landing.flame_species(limit=1), [{"name": "C3H4-P", "models": 2, "subscripts": True}])

    def test_only_digits_that_count_atoms_become_subscripts(self):
        cases = {
            ("CH3OH", "CH4O"): True, ("C3H5-A", "C3H5"): True, ("CH2(S)", "CH2"): True,
            ("HOCHO", "CH2O2"): True, ("C10H22", "C10H22"): True, ("Ar", "Ar"): True,
            # Locants, isomer prefixes and other mnemonics keep their digits full size
            ("C4H71-4", "C4H7"): False, ("C2H4O1-2", "C2H4O"): False, ("C4H612", "C4H6"): False,
            ("NC3H7", "C3H7"): False, ("IC4H9", "C4H9"): False, ("C3KET21", "C3H5O3"): False,
            ("AR", "Ar"): False, ("nC3H7", "C3H7"): False,
        }
        for (name, formula), expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(landing.name_spells_formula(name, {formula}), expected)

    def test_home_page_shows_live_numbers(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        numbers = response.context["numbers"]
        self.assertEqual(numbers["models"], "2")
        self.assertEqual(numbers["propyne_names"], "3")
        self.assertEqual(numbers["shared_name_models"], "1")
        allene = next(m for m in response.context["scene"] if m["key"] == "allene")
        self.assertEqual(allene["shared_name_models"], 1)
        self.assertContains(response, "The models in Prometheus use 3 names for propyne and 1 names for allene.")
        self.assertNotContains(response, "{propyne_names}")
        self.assertContains(response, 'id="lp-flame-species"')
        self.assertContains(response, "is one of the 3 species that the most models in Prometheus use.")
