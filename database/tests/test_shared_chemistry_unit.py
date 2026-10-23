from collections import Counter

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rmgpy import kinetics as rmg_kinetics
from rmgpy.molecule import Molecule

from database import models
from database.scripts.import_rmg_models import create_kinetics_data
from database.services import chemistry_index, shared_chemistry, sub_mechanisms
from database.services import thermo_sources as sources


def rate(A):
    return create_kinetics_data(None, rmg_kinetics.Arrhenius(A=(A, "cm^3/(mol*s)"), n=0, Ea=(10, "kcal/mol"), T0=(1, "K")), None)


class ClusteringTests(SimpleTestCase):
    def test_average_linkage_stops_below_threshold(self):
        base = {key: "rate" for key in "abcdefghij"}
        edited = dict(base, j="other rate")                 # 9 of 10 reactions identical
        rewritten = {key: "own rate" for key in "abcdefghij"}  # same reactions, none identical
        self.assertEqual(sub_mechanisms.cluster({1: base, 2: edited, 3: rewritten}), [[1, 2], [3]])

    def test_layer_order(self):
        layers = ["C1+N", "N", "C2", "H2/O2", "C≥4", "C1"]
        self.assertEqual(sorted(layers, key=sub_mechanisms.layer_sort_key), ["H2/O2", "C1", "C2", "C≥4", "N", "C1+N"])


class SharedChemistryTests(TestCase):
    def species(self, smiles):
        return sources._species_and_structure(Molecule().from_smiles(smiles), smiles)[0]

    def reaction(self, reactants, products):
        reaction = models.Reaction.objects.create(hash="-".join(str(s.pk) for s in reactants + products), reversible=True)
        for side, sign in ((reactants, -1), (products, 1)):
            for species, count in Counter(side).items():
                models.Stoichiometry.objects.create(reaction=reaction, species=species, coeff=sign * count)
        return reaction

    def model(self, name, year):
        source = models.Source.objects.create(publication_year=str(year), source_title=name)
        return models.KineticModel.objects.create(model_name=name, source=source)

    def use(self, model, reaction, A):
        kinetics, _ = models.Kinetics.objects.get_or_create(reaction=reaction, raw_data=rate(A))
        models.KineticsComment.objects.create(kinetics=kinetics, kinetic_model=model, comment="")

    def setUp(self):
        self.core = self.model("Core 2010", 2010)
        self.copy = self.model("Copy 2015", 2015)
        self.other = self.model("Other 2016", 2016)
        h, o2, oh, o, h2, h2o, ho2, h2o2, ch4, ch3 = (self.species(s) for s in (
            "[H]", "[O][O]", "[OH]", "[O]", "[H][H]", "O", "[O]O", "OO", "C", "[CH3]"))
        # Twelve distinct H2/O2 reactions (no reverse duplicates), enough for one block.
        pairs = [([h, o2], [oh, o]), ([o, h2], [oh, h]), ([oh, h2], [h2o, h]), ([oh, oh], [h2o, o]),
                 ([h, h], [h2]), ([o, o], [o2]), ([h, oh], [h2o]), ([h, o], [oh]), ([h, ho2], [oh, oh]),
                 ([o2, h2], [oh, oh]), ([h, ho2], [h2, o2]), ([h2o2], [oh, oh])]
        self.h2o2 = [self.reaction(r, p) for r, p in pairs]
        self.c1 = self.reaction([ch4, h], [ch3, h2])
        for index, reaction in enumerate(self.h2o2):
            self.use(self.core, reaction, 1e12 + index)
            self.use(self.copy, reaction, 1e12 + index)       # copied unchanged
            self.use(self.other, reaction, 5e12 + index)      # same reactions, other rates
        self.use(self.copy, self.c1, 1e13)
        chemistry_index.index_reactions()
        chemistry_index.index_kinetics()

    def test_overlap_blocks_and_lineage(self):
        counts = shared_chemistry.analyze()
        self.assertEqual(counts["blocks"], 1)
        row = models.SharedChemistry.objects.get(model_a=self.copy, model_b=self.core, layer="H2/O2")
        self.assertEqual((row.reactions, row.shared, row.identical), (12, 12, 12))
        other = models.SharedChemistry.objects.get(model_a=self.other, model_b=self.core, layer="H2/O2")
        self.assertEqual((other.shared, other.identical), (12, 0))
        self.assertEqual(models.SharedChemistry.objects.get(model_a=self.copy, model_b=self.core, layer="all").reactions, 13)
        block = models.ChemistryBlock.objects.get()
        self.assertEqual((block.size, block.origin, set(block.kinetic_models.all())), (12, self.core, {self.core, self.copy}))
        self.assertEqual(block.layers, {"H2/O2": 12})
        self.assertEqual(shared_chemistry.lineage(self.copy)["H2/O2"].model_b, self.core)
        self.assertNotIn("H2/O2", shared_chemistry.lineage(self.core))

    def test_pages(self):
        shared_chemistry.analyze()
        page = self.client.get(reverse("kinetic-model-detail", args=[self.copy.pk]))
        self.assertContains(page, "Shared chemistry")
        self.assertContains(page, f'earliest <a href="{reverse("kinetic-model-detail", args=[self.core.pk])}">Core 2010</a>')
        self.assertContains(page, "shared by 2 models")
        block = models.ChemistryBlock.objects.get()
        self.assertContains(page, reverse("chemistry-block-detail", args=[block.pk]))
        block_page = self.client.get(reverse("chemistry-block-detail", args=[block.pk]))
        self.assertContains(block_page, "12 identical rates shared by 2 models")
        self.assertContains(block_page, reverse("kinetic-model-detail", args=[self.copy.pk]))
        self.assertContains(block_page, reverse("reaction-detail", args=[self.h2o2[0].pk]))
        compare = self.client.get(reverse("kinetic-model-compare"), {"a": self.other.pk, "b": self.core.pk})
        self.assertContains(compare, "Shared reactions with different rates (12)")
        similarity = self.client.get(reverse("kinetic-model-similarity"), {"layer": "H2/O2"})
        self.assertContains(similarity, 'id="similarity-data"')
        self.assertContains(similarity, "Copy 2015")

    def test_duplicate_expressions_compare_as_their_sum(self):
        reaction = self.c1
        halves = [rmg_kinetics.Arrhenius(A=(A, "cm^3/(mol*s)"), n=0, Ea=(10, "kcal/mol"), T0=(1, "K")) for A in (1e12, 2e12)]
        split = self.model("Split duplicates", 2018)
        merged = self.model("Merged duplicates", 2019)
        for half in halves:
            kinetics, _ = models.Kinetics.objects.get_or_create(reaction=reaction, raw_data=create_kinetics_data(None, half, None))
            models.KineticsComment.objects.create(kinetics=kinetics, kinetic_model=split, comment="")
        total = models.Kinetics.objects.create(reaction=reaction, raw_data=create_kinetics_data(
            None, rmg_kinetics.MultiArrhenius(arrhenius=halves), None))
        models.KineticsComment.objects.create(kinetics=total, kinetic_model=merged, comment="")
        chemistry_index.index_kinetics()
        shared_chemistry.analyze()
        row = models.SharedChemistry.objects.get(model_a=split, model_b=merged, layer="all")
        self.assertEqual((row.reactions, row.identical), (1, 1))

    def test_sub_mechanisms_and_variants(self):
        edit = self.model("Edit 2017", 2017)
        for index, reaction in enumerate(self.h2o2):
            self.use(edit, reaction, 1e12 + index if index < 10 else 9e12 + index)   # two rates changed
        chemistry_index.index_kinetics()
        counts = shared_chemistry.analyze()
        # The copy's one C1 reaction is too little to be a sub-mechanism.
        self.assertEqual((counts["sub_mechanisms"], counts["shared"], counts["variants"]), (2, 1, 3))
        family = models.SubMechanism.objects.get(layer="H2/O2", origin=self.core)
        self.assertEqual((family.default_name, family.model_count, family.variant_count, family.reactions, family.core),
                         ("Core 2010 H2/O2", 3, 2, 12, 10))
        first, second = family.variants.all()
        self.assertEqual(set(first.kinetic_models.all()), {self.core, self.copy})   # identical rates: one variant
        self.assertEqual((second.representative, second.identical, second.changed, second.added, second.missing),
                         (edit, 10, 2, 0, 0))
        lone = models.SubMechanism.objects.get(layer="H2/O2", origin=self.other)
        self.assertEqual((lone.model_count, lone.variant_count), (1, 1))

        family.name = "Core H2/O2"
        family.save()
        shared_chemistry.analyze()
        self.assertEqual(models.SubMechanism.objects.get(pk=family.pk).name, "Core H2/O2")

        detail = self.client.get(reverse("sub-mechanism-detail", args=[family.pk]))
        self.assertContains(detail, "Core H2/O2")
        self.assertContains(detail, "2 of 12 reactions differ between variants")
        self.assertContains(detail, "rate-tone-1")
        self.assertContains(detail, 'id="variant-data"')
        against_edit = self.client.get(reverse("sub-mechanism-detail", args=[family.pk]), {"reference": 2})
        self.assertContains(against_edit, "Same rate as v2")
        listing = self.client.get(reverse("sub-mechanism-list"))
        self.assertContains(listing, "Core H2/O2")
        self.assertContains(listing, "Other 2016 H2/O2")
        self.assertNotContains(self.client.get(reverse("sub-mechanism-list"), {"shared": "1"}), "Other 2016 H2/O2")
        self.assertContains(self.client.get(reverse("kinetic-model-detail", args=[self.copy.pk])), "v1 of 2")
