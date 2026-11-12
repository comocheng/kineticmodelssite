"""The species page and the species search say which structure is which when a species has
resonance structures (one molecule drawn more than one way, one InChIKey and multiplicity)."""
from urllib.parse import quote

from django.test import TestCase

from database import models as db

KEY = "ZQHGTWBTOVSLEJ-UHFFFAOYSA-N-2"


class ResonanceLabelTests(TestCase):
    def setUp(self):
        formula = db.Formula.objects.create(formula="C4H5")
        self.species = db.Species.objects.create(hash="hash-iC4H5")
        self.structures = []
        for suffix, smiles in (("u4", "C=[C]C=C"), ("u1", "[CH2]C=C=C")):
            isomer = db.Isomer.objects.create(formula=formula, inchi=f"InChI=1S/C4H5/c1-3-4-2/h3H,1-2H2/{suffix}")
            self.species.isomers.add(isomer)
            structure = db.Structure.objects.create(isomer=isomer, multiplicity=2, smiles=smiles,
                                                    adjacency_list=f"fixture {smiles}")
            # save() computes the key from the adjacency list, which a fixture does not have.
            db.Structure.objects.filter(pk=structure.pk).update(structure_key=KEY, canonical_smiles=smiles)
            self.structures.append(structure)
        model = db.KineticModel.objects.create(model_name="Fixture")
        db.SpeciesName.objects.create(kinetic_model=model, species=self.species, name="iC4H5")

    def search(self, query):
        return self.client.get(f"/species_search/?q={quote(query)}")

    def test_species_page_names_the_resonance_structures_and_their_ids(self):
        response = self.client.get(f"/species/{self.species.pk}")
        self.assertContains(response, "2 resonance structures")
        self.assertContains(response, "These are resonance structures of one molecule")
        for structure in self.structures:
            self.assertContains(response, f"?q=structure:{structure.pk}\">{structure.pk}</a>")
        self.assertContains(response, "one of 2 resonance structures", count=2)

    def test_search_shows_the_structure_it_matched(self):
        second = self.structures[1]
        response = self.search("smiles:[CH2]C=C=C")
        self.assertContains(response, f"Matched structure <span class=\"sp-match__id\">{second.pk}</span>")
        self.assertContains(response, "one of 2 resonance structures of this species")
        self.assertContains(response, f"/drawstructure/{second.pk}")          # its drawing, not the first one
        self.assertNotContains(response, f"/drawstructure/{self.structures[0].pk}\"")
        response = self.search(f"structure:{self.structures[0].pk}")
        self.assertContains(response, f"Matched structure <span class=\"sp-match__id\">{self.structures[0].pk}</span>")

    def test_search_by_name_shows_no_match_line(self):
        self.assertNotContains(self.search("iC4H5"), "Matched structure")

    def test_structure_search_given_a_species_id_says_so(self):
        structure_ids = set(db.Structure.objects.values_list("pk", flat=True))
        species = self.species
        while species.pk in structure_ids:
            species = db.Species.objects.create(hash=f"hash-{species.pk}")
        response = self.search(f"structure:{species.pk}")
        self.assertContains(response, f"No structure has the ID {species.pk}")
        self.assertContains(response, f"href=\"/species/{species.pk}\"")
        response = self.search("structure:999999")
        self.assertNotContains(response, "No structure has the ID")       # not a species id either


CARBOXYMETHYL = (
    ("[CH2]C(=O)O", "RSKSXHOOZARWIX-UHFFFAOYSA-N-2",
     "multiplicity 2\n1 C u1 p0 c0 {2,S} {5,S} {6,S}\n2 C u0 p0 c0 {1,S} {3,D} {4,S}\n3 O u0 p2 c0 {2,D}\n"
     "4 O u0 p2 c0 {2,S} {7,S}\n5 H u0 p0 c0 {1,S}\n6 H u0 p0 c0 {1,S}\n7 H u0 p0 c0 {4,S}"),
    ("C=C([O])O", "YPDDEXGOBNLPGT-UHFFFAOYSA-N-2",
     "multiplicity 2\n1 C u0 p0 c0 {2,D} {5,S} {6,S}\n2 C u0 p0 c0 {1,D} {3,S} {4,S}\n3 O u1 p2 c0 {2,S}\n"
     "4 O u0 p2 c0 {2,S} {7,S}\n5 H u0 p0 c0 {1,S}\n6 H u0 p0 c0 {1,S}\n7 H u0 p0 c0 {4,S}"),
)
NOT_ONE = (
    ("[H][H]", "UFHFLCQGNIYNRP-UHFFFAOYSA-N-1", "1 H u0 p0 c0 {2,S}\n2 H u0 p0 c0 {1,S}"),
    ("O", "XLYOFNOQVPJJNP-UHFFFAOYSA-N-1", "1 O u0 p2 c0 {2,S} {3,S}\n2 H u0 p0 c0 {1,S}\n3 H u0 p0 c0 {1,S}"),
)


def species_with(name, rows, multiplicity=2, state=""):
    record = db.Species.objects.create(hash=f"hash-{name}", electronic_state=state)
    for index, (smiles, key, adjacency) in enumerate(rows):
        formula, _ = db.Formula.objects.get_or_create(formula=f"F{name}{index}")
        isomer = db.Isomer.objects.create(formula=formula, inchi=f"InChI=1S/{name}/{index}")
        record.isomers.add(isomer)
        structure = db.Structure.objects.create(isomer=isomer, multiplicity=multiplicity, smiles=smiles,
                                                adjacency_list=adjacency)
        db.Structure.objects.filter(pk=structure.pk).update(structure_key=key)
    return record


class ResonanceAcrossKeysTests(TestCase):
    def test_resonance_structures_with_two_inchikeys_are_one_molecule(self):
        record = species_with("carboxymethyl", CARBOXYMETHYL)
        response = self.client.get(f"/species/{record.pk}")
        self.assertContains(response, "2 resonance structures")
        self.assertContains(response, "Their InChIKeys differ because InChI tells some resonance structures apart")
        self.assertNotContains(response, "needs to be checked")

    def test_two_molecules_in_one_species_are_flagged(self):
        record = species_with("mixed", NOT_ONE, multiplicity=1)
        response = self.client.get(f"/species/{record.pk}")
        self.assertContains(response, "The identification of this species needs to be checked")
        self.assertNotContains(response, "These are resonance structures")


class ExcitedStateTests(TestCase):
    def setUp(self):
        formula = db.Formula.objects.create(formula="HO")
        isomer = db.Isomer.objects.create(formula=formula, inchi="InChI=1S/HO/h1H")
        db.Structure.objects.create(isomer=isomer, multiplicity=2, smiles="[OH]", adjacency_list="fixture OH")
        db.Structure.objects.filter(isomer=isomer).update(structure_key="TUJKJAMUKRIRHC-UHFFFAOYSA-N-2")
        self.ground = db.Species.objects.create(hash="hash-OH")
        self.excited = db.Species.objects.create(hash="hash-OH*", electronic_state="excited")
        for record in (self.ground, self.excited):
            record.isomers.add(isomer)

    def test_excited_state_page_says_so_and_links_the_ground_state(self):
        response = self.client.get(f"/species/{self.excited.pk}")
        self.assertContains(response, "This species is an electronically excited state.")
        self.assertContains(response, f"<a href=\"/species/{self.ground.pk}\">species {self.ground.pk}</a>")
        self.assertNotContains(response, "needs to be checked")
        self.assertNotContains(response, "excited: excited")

    def test_ground_state_page_links_its_excited_states(self):
        response = self.client.get(f"/species/{self.ground.pk}")
        self.assertContains(response, "Electronically excited states of this molecule are separate species")
        self.assertContains(response, f"<a href=\"/species/{self.excited.pk}\">species {self.excited.pk}</a>")

    def test_search_marks_the_excited_state(self):
        response = self.client.get("/species_search/?q=smiles:[OH]")
        self.assertContains(response, "excited state</span>", count=1)
