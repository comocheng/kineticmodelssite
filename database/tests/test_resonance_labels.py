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
