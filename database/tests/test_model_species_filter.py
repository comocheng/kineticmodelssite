"""/api/kineticmodel/?species= selects the models whose species list contains the species."""

from django.test import TestCase

from database import models


def make_species(inchi):
    formula = models.Formula.objects.create(formula=inchi.split("/")[1])
    isomer = models.Isomer.objects.create(inchi=inchi, formula=formula)
    species = models.Species.objects.create(hash=inchi)
    species.isomers.add(isomer)
    return species


def make_model(name, *species_names):
    model = models.KineticModel.objects.create(model_name=name, source=models.Source.objects.create())
    for species, label in species_names:
        models.SpeciesName.objects.create(kinetic_model=model, species=species, name=label)
    return model


class KineticModelSpeciesFilterTests(TestCase):
    def setUp(self):
        self.h2 = make_species("InChI=1S/H2/h1H")
        self.nh3 = make_species("InChI=1S/H3N/h1H3")
        self.both = make_model("both", (self.h2, "H2"), (self.nh3, "NH3"))
        self.h2_only = make_model("h2 only", (self.h2, "H2"))
        # The same species under two names in one model
        self.nh3_twice = make_model("nh3 twice", (self.nh3, "NH3"), (self.nh3, "AMMONIA"))

    def _names(self, query):
        response = self.client.get(f"/api/kineticmodel/?{query}")
        self.assertEqual(response.status_code, 200, response.content[:300])
        return sorted(r["model_name"] for r in response.json()["results"])

    def test_one_species(self):
        self.assertEqual(self._names(f"species={self.h2.pk}"), ["both", "h2 only"])

    def test_every_species_given_must_be_in_the_model(self):
        self.assertEqual(self._names(f"species={self.h2.pk}&species={self.nh3.pk}"), ["both"])

    def test_a_model_is_listed_once(self):
        self.assertEqual(self._names(f"species={self.nh3.pk}"), ["both", "nh3 twice"])

    def test_unknown_species_is_an_error(self):
        response = self.client.get("/api/kineticmodel/?species=999999")
        self.assertEqual(response.status_code, 400)
