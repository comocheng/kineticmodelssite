"""Canonical keys and URLs of the records: the keys, the resolver /id/<kind>/<key>, the redirects and
tombstones of changed and removed records, and the key fields and ?key= filter of the API."""
import io

from django.core.management import call_command
from django.test import TestCase

from database import models as db
from database.services.chemistry_index import index_reactions
from provenance.models import RecordKey
from provenance.record_key_sync import assign
from provenance.record_keys import KINDS, normal_doi

RATE = {"type": "Arrhenius", "A": 1e14, "n": 0, "Ea": 0}
POLY = {"coeffs_poly1": [3.5, 0, 0, 0, 0, 100.0, 1.0], "coeffs_poly2": [3.5, 0, 0, 0, 0, 100.0, 1.0],
        "temp_min_1": 298.0, "temp_max_1": 1000.0, "temp_min_2": 1000.0, "temp_max_2": 5000.0}
H2 = "UFHFLCQGNIYNRP-UHFFFAOYSA-N-1"
OH = "TUJKJAMUKRIRHC-UHFFFAOYSA-N-2"
H2O = "XLYOFNOQVPJJNP-UHFFFAOYSA-N-1"
H = "YZCKVEUIGOORGS-UHFFFAOYSA-N-2"


def species(name, inchi, key, multiplicity=1):
    formula, _ = db.Formula.objects.get_or_create(formula=inchi.split("/")[1])
    isomer, _ = db.Isomer.objects.get_or_create(formula=formula, inchi=inchi)
    record = db.Species.objects.create(hash=f"hash-{name}")
    record.isomers.add(isomer)
    structure, _ = db.Structure.objects.get_or_create(isomer=isomer, multiplicity=multiplicity,
                                                      defaults={"smiles": name, "adjacency_list": f"fixture {name}"})
    # save() computes the key from the adjacency list, which a fixture does not have.
    db.Structure.objects.filter(pk=structure.pk).update(structure_key=key)
    model, _ = db.KineticModel.objects.get_or_create(model_name="Fixture/model one")
    db.SpeciesName.objects.create(kinetic_model=model, species=record, name=name)
    return record


def reaction(*rows):
    row = db.Reaction.objects.create(hash="hash-" + "".join(f"{c}{s.pk}" for c, s in rows), reversible=True)
    for coeff, record in rows:
        db.Stoichiometry.objects.create(reaction=row, species=record, coeff=coeff)
    return row


def assign_all():
    for kind in KINDS:
        assign(kind, apply=True)


class RecordKeyTests(TestCase):
    def setUp(self):
        self.h2 = species("H2", "InChI=1S/H2/h1H", H2)
        self.oh = species("OH", "InChI=1S/HO/h1H/u1", OH, multiplicity=2)
        self.h2o = species("H2O", "InChI=1S/H2O/h1H2", H2O)
        self.h = species("H", "InChI=1S/H/u1", H, multiplicity=2)
        self.forward = reaction((-1, self.h2), (-1, self.oh), (1, self.h2o), (1, self.h))
        self.backward = reaction((-1, self.h), (-1, self.h2o), (1, self.h2), (1, self.oh))
        index_reactions(refresh=True)
        self.rate = db.Kinetics.objects.create(reaction=self.forward, raw_data=RATE)
        self.thermo = db.Thermo.objects.create(species=self.oh, **POLY)
        self.source = db.Source.objects.create(doi="https://doi.org/10.1016/J.Combustflame.2020.01.001")
        assign_all()

    def key_of(self, kind, record):
        return RecordKey.objects.get(kind=kind, object_id=record.pk, status="current").key

    # --- the keys -------------------------------------------------------------------------
    def test_keys_come_from_the_chemistry_not_the_row(self):
        self.assertEqual(self.key_of("species", self.oh), OH)
        self.assertEqual(self.key_of("structure", self.oh.structures.first()), OH)
        left, right = sorted(["+".join(sorted([H2, OH])), "+".join(sorted([H2O, H]))])
        chemistry = f"{left}={right}"
        directions = {self.key_of("reaction", self.forward), self.key_of("reaction", self.backward)}
        self.assertEqual(directions, {f"{chemistry}/f", f"{chemistry}/r"})
        self.assertTrue(self.key_of("kinetics", self.rate).startswith(self.key_of("reaction", self.forward) + "/"))
        self.assertTrue(self.key_of("thermo", self.thermo).startswith(OH + "/"))
        self.assertEqual(self.key_of("source", self.source), "10.1016/j.combustflame.2020.01.001")
        self.assertEqual(self.key_of("kineticmodel", db.KineticModel.objects.get()), "Fixture/model one")

    def test_rebuild_gives_the_same_url(self):
        old_key, old_pk = self.key_of("species", self.oh), self.oh.pk
        db.Thermo.objects.filter(species=self.oh).delete()
        db.Reaction.objects.all().delete()
        self.oh.delete()
        again = species("OH", "InChI=1S/HO/h1H/u1", OH, multiplicity=2)
        assign_all()
        self.assertNotEqual(again.pk, old_pk)
        response = self.client.get(f"/id/species/{old_key}")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], f"/species/{again.pk}")

    def test_chebyshev_range_is_part_of_the_key(self):
        # PCI2017/111-Jin writes the coefficients of CombFlame2013/1939-Cai with 270-3000 K, not 290-3000 K.
        cheb = {"type": "chebyshev", "coefficient_matrix": [[11.5, 0.52], [-0.62, 0.31]], "units": "cm^3/(mol*s)"}
        bar = {"min_pressure": 1e3, "max_pressure": 1e7}
        a = db.Kinetics.objects.create(reaction=self.forward, raw_data=cheb, min_temp=290.0, max_temp=3000.0, **bar)
        b = db.Kinetics.objects.create(reaction=self.forward, raw_data=cheb, min_temp=270.0, max_temp=3000.0, **bar)
        assign("kinetics", apply=True)
        self.assertNotEqual(self.key_of("kinetics", a), self.key_of("kinetics", b))

    def test_other_rate_keeps_its_key_when_its_range_changes(self):
        key = self.key_of("kinetics", self.rate)
        db.Kinetics.objects.filter(pk=self.rate.pk).update(min_temp=200.0, max_temp=2500.0)
        assign("kinetics", apply=True)
        self.assertEqual(self.key_of("kinetics", self.rate), key)

    def test_dry_run_writes_nothing(self):
        db.Source.objects.create(doi="10.1/new")
        before = RecordKey.objects.count()
        out = io.StringIO()
        call_command("assign_record_keys", "--kind", "source", stdout=out)
        self.assertEqual(RecordKey.objects.count(), before)
        self.assertIn("new 1", out.getvalue())

    def test_no_identity_no_key(self):
        db.Source.objects.create(doi="")
        db.Source.objects.create(doi="not a doi")
        self.assertEqual(normal_doi("doi:10.5/X"), "10.5/x")
        assign("source", apply=True)
        self.assertEqual(RecordKey.objects.filter(kind="source").count(), 1)

    # --- the resolver ---------------------------------------------------------------------
    def test_one_record_redirects_to_its_page_or_api_record(self):
        response = self.client.get(f"/id/species/{OH}")
        self.assertEqual((response.status_code, response["Location"]), (303, f"/species/{self.oh.pk}"))
        self.assertIn("no-cache", response["Cache-Control"])
        response = self.client.get(f"/id/species/{OH}", HTTP_ACCEPT="application/json")
        self.assertEqual((response.status_code, response["Location"]), (303, f"/api/species/{self.oh.pk}/"))
        structure = self.oh.structures.first()
        response = self.client.get(f"/id/structure/{OH}")
        self.assertEqual(response["Location"], f"/api/structure/{structure.pk}/")

    def test_model_name_with_a_slash_resolves(self):
        model = db.KineticModel.objects.get()
        response = self.client.get("/id/kineticmodel/Fixture/model%20one")
        self.assertEqual((response.status_code, response["Location"]), (303, f"/kineticmodel/{model.pk}"))

    def test_reaction_without_direction_lists_both(self):
        chemistry = self.key_of("reaction", self.forward)[:-2]
        response = self.client.get(f"/id/reaction/{chemistry}")
        self.assertEqual(response.status_code, 300)
        self.assertContains(response, "2 records have this key", status_code=300)
        data = self.client.get(f"/id/reaction/{chemistry}?format=json").json()
        self.assertEqual({r["key"][-2:] for r in data["records"]}, {"/f", "/r"})

    def test_reaction_without_direction_and_one_record_redirects(self):
        chemistry = self.key_of("reaction", self.forward)[:-2]
        self.backward.delete()
        assign("reaction", apply=True)
        response = self.client.get(f"/id/reaction/{chemistry}")
        self.assertEqual((response.status_code, response["Location"]), (303, f"/reaction/{self.forward.pk}"))

    def test_changed_identity_redirects_from_the_old_key(self):
        db.Structure.objects.filter(isomer__species=self.oh).update(structure_key="NEWKEY-UHFFFAOYSA-N-2")
        assign("species", apply=True)
        response = self.client.get(f"/id/species/{OH}")
        self.assertEqual((response.status_code, response["Location"]), (301, "/id/species/NEWKEY-UHFFFAOYSA-N-2"))
        self.assertIn("max-age=86400", response["Cache-Control"])
        self.assertEqual(self.client.get(response["Location"]).status_code, 303)

    def test_removed_record_leaves_a_tombstone(self):
        key = self.key_of("source", self.source)
        self.source.delete()
        assign("source", apply=True)
        response = self.client.get(f"/id/source/{key}")
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "no longer in the database", status_code=410)
        data = self.client.get(f"/id/source/{key}?format=json").json()
        self.assertEqual((data["status"], data["reason"]), ("retired", "record removed"))

    def test_merged_record_resolves_to_the_one_left(self):
        # The same molecule twice, as an older import left it: two isomer rows with one InChIKey.
        twin = species("OH2", "InChI=1S/HO/h1H/u1/twin", OH, multiplicity=2)
        assign("species", apply=True)
        self.assertEqual(self.client.get(f"/id/species/{OH}").status_code, 300)
        db.Thermo.objects.filter(species=self.oh).delete()
        db.Reaction.objects.all().delete()
        self.oh.delete()                                                    # the merge keeps the twin
        assign("species", apply=True)
        response = self.client.get(f"/id/species/{OH}")
        self.assertEqual((response.status_code, response["Location"]), (303, f"/species/{twin.pk}"))

    def test_unknown_kind_or_key_is_404(self):
        self.assertEqual(self.client.get("/id/planet/earth").status_code, 404)
        self.assertEqual(self.client.get("/id/species/NOPE").status_code, 404)

    # --- the API ----------------------------------------------------------------------------
    def test_api_record_gives_key_and_canonical_url(self):
        data = self.client.get(f"/api/species/{self.oh.pk}/").json()
        self.assertEqual(data["key"], OH)
        self.assertTrue(data["canonical_url"].endswith(f"/id/species/{OH}"))
        rows = self.client.get("/api/source/").json()["results"]
        self.assertEqual(rows[0]["key"], "10.1016/j.combustflame.2020.01.001")

    def test_api_filter_by_key(self):
        rows = self.client.get(f"/api/species/?key={OH}").json()["results"]
        self.assertEqual([row["id"] for row in rows], [self.oh.pk])
        chemistry = self.key_of("reaction", self.forward)[:-2]
        rows = self.client.get("/api/reaction/", {"key": chemistry}).json()["results"]
        self.assertEqual({row["id"] for row in rows}, {self.forward.pk, self.backward.pk})
        self.assertEqual(self.client.get("/api/species/?kee=x").status_code, 400)

    def test_openapi_documents_the_key(self):
        schema = self.client.get("/api/schema/?format=json").json()
        params = {p["name"] for p in schema["paths"]["/api/species/"]["get"]["parameters"]}
        self.assertIn("key", params)
        self.assertIn("canonical_url", schema["components"]["schemas"]["Species"]["properties"])
