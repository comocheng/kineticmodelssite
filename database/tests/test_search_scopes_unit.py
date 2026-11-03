from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from database.models import Formula, Isomer, KineticModel, Reaction, Source, Species, Stoichiometry, Structure
from database.services.reaction_search import filter_reactions, species_terms
from database.views import SEARCH_SCOPES


class SpeciesTermsTests(SimpleTestCase):
    def test_equations_split_into_species(self):
        self.assertEqual(species_terms("H + O2"), ["H", "O2"])
        self.assertEqual(species_terms("H + O2 <=> O + OH"), ["H", "O2", "O", "OH"])
        self.assertEqual(species_terms("CH3 + HO2 = CH3O + OH"), ["CH3", "HO2", "CH3O", "OH"])

    def test_third_bodies_name_no_species(self):
        self.assertEqual(species_terms("H + O2 (+M)"), ["H", "O2"])
        self.assertEqual(species_terms("H2O2(+M) => OH + OH"), ["H2O2", "OH", "OH"])
        self.assertEqual(species_terms("H + O2 + M"), ["H", "O2"])

    def test_a_plus_inside_a_name_stays(self):
        self.assertEqual(species_terms("H3O+"), ["H3O+"])
        self.assertEqual(species_terms("  "), [])


class ReactionSpeciesSearchTests(TestCase):
    @classmethod
    def add_species(cls, name, formula, smiles):
        formula, _ = Formula.objects.get_or_create(formula=formula)
        isomer = Isomer.objects.create(formula=formula, inchi=f"InChI=fixture/{name}")
        Structure.objects.create(isomer=isomer, smiles=smiles, adjacency_list=f"fixture {name}",
                                 multiplicity=1, iupac_name=name)
        species = Species.objects.create(hash=name)
        species.isomers.add(isomer)
        return species

    @classmethod
    def add_reaction(cls, label, reactants, products):
        reaction = Reaction.objects.create(hash=label, reversible=True)
        for species in reactants:
            Stoichiometry.objects.create(reaction=reaction, species=species, coeff=-1)
        for species in products:
            Stoichiometry.objects.create(reaction=reaction, species=species, coeff=1)
        return reaction

    @classmethod
    def setUpTestData(cls):
        h = cls.add_species("hydrogen atom", "H", "[H]")
        o2 = cls.add_species("oxygen", "O2", "O=O")
        o = cls.add_species("oxygen atom", "O", "[O]")
        oh = cls.add_species("hydroxyl", "HO", "[OH]")
        ho2 = cls.add_species("hydroperoxyl", "HO2", "O[O]")
        ch4 = cls.add_species("methane", "CH4", "C")
        ch3 = cls.add_species("methyl", "CH3", "[CH3]")
        h2o = cls.add_species("water", "H2O", "O")
        cls.branching = cls.add_reaction("branching", [h, o2], [o, oh])
        cls.recombination = cls.add_reaction("recombination", [h, o2], [ho2])
        cls.abstraction = cls.add_reaction("abstraction", [ch4, oh], [ch3, h2o])

    def search(self, value):
        return set(filter_reactions(Reaction.objects.all(), value))

    def test_one_species_finds_it_on_either_side(self):
        self.assertEqual(self.search("OH"), {self.branching, self.abstraction})
        self.assertEqual(self.search("methane"), {self.abstraction})

    def test_every_species_of_an_equation_must_appear(self):
        self.assertEqual(self.search("H + O2"), {self.branching, self.recombination})
        self.assertEqual(self.search("H + O2 <=> O + OH"), {self.branching})
        self.assertEqual(self.search("H + O2 (+M)"), {self.branching, self.recombination})

    def test_a_species_with_no_match_finds_no_reaction(self):
        self.assertEqual(self.search("CH4 + unobtainium"), set())

    def test_page_names_the_species_and_keeps_them_for_the_filters(self):
        response = self.client.get(reverse("reaction-search"), {"species": "CH4 + OH"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["object_list"]), [self.abstraction])
        self.assertContains(response, "that includes")
        self.assertContains(response, '<span class="rx-results__term">CH4</span> and <span class="rx-results__term">OH</span>')
        self.assertContains(response, '<input type="hidden" name="species" value="CH4 + OH">', html=True)

    def test_page_says_which_species_matches_nothing(self):
        response = self.client.get(reverse("reaction-search"), {"species": "unobtainium"})
        self.assertContains(response, "No species matches “unobtainium”")


class KineticModelSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = Source.objects.create()
        KineticModel.objects.create(model_name="GRI-mech-3.0", source=source)
        KineticModel.objects.create(model_name="AramcoMech_2.0", source=source, prime_id="m00000002")

    def names(self, query):
        response = self.client.get(reverse("kinetic-model-list"), {"q": query})
        return [model.model_name for model in response.context["object_list"]]

    def test_name_and_prime_id(self):
        self.assertEqual(self.names("gri"), ["GRI-mech-3.0"])
        self.assertEqual(self.names("m00000002"), ["AramcoMech_2.0"])
        self.assertEqual(self.names(""), ["GRI-mech-3.0", "AramcoMech_2.0"])
        self.assertEqual(self.names("nothing"), [])


class DatabaseSearchScopeTests(TestCase):
    def test_every_scope_sends_its_examples_to_its_own_search(self):
        response = self.client.get(reverse("database-home"))
        self.assertEqual(response.status_code, 200)
        scopes = response.context["search_scopes"]
        self.assertEqual([scope["key"] for scope in scopes], [scope["key"] for scope in SEARCH_SCOPES])
        for scope in scopes:
            with self.subTest(scope=scope["key"]):
                self.assertContains(response, f'data-scope="{scope["key"]}"')
                for example in scope["examples"]:
                    self.assertTrue(example["href"].startswith(f'{scope["action"]}?{scope["param"]}='))
                    self.assertEqual(self.client.get(example["href"]).status_code, 200)
