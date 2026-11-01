import os
import shutil
import tempfile
from unittest import mock

from django.test import TestCase
from rmgpy.molecule import Molecule

from database import models as db
from database.scripts.import_rmg_models import (
    get_or_create_species, get_reaction_hash, get_species_hash, import_kinetics, import_thermo)
from database.services import cleanup
from database.tests.test_import_rmg_species_unit import MODELS, model_folder, molecule, resonance_forms

FIELDS = {"coeffs_poly1": [3.5, 0, 0, 0, 0, 100.0, 1.0], "coeffs_poly2": [3.5, 0, 0, 0, 0, 100.0, 1.0],
          "temp_min_1": 298.0, "temp_max_1": 1000.0, "temp_min_2": 1000.0, "temp_max_2": 5000.0}
RATE = {"type": "Arrhenius", "A": 1e14, "n": 0, "Ea": 0}


def split_records(label="HCCO"):
    """The two records an older import left for one radical: one resonance form (from a thermo
    entry) and the full set (from a reaction)."""
    forms = resonance_forms(label)
    get_or_create_species(None, "", forms, MODELS)
    isomers = list(db.Isomer.objects.filter(formula__formula=forms[0].get_formula()).order_by("pk"))
    db.Species.objects.filter(isomers__in=isomers).delete()
    single = db.Species.objects.create(hash="single")
    single.isomers.add(isomers[0])
    full = db.Species.objects.create(hash="full")
    full.isomers.add(*isomers)
    return single, full


def reaction(*rows):
    """A reaction from (coeff, species) rows, as the importer stores it."""
    row = db.Reaction.objects.create(hash=get_reaction_hash(rows), reversible=True)
    for coeff, species in rows:
        db.Stoichiometry.objects.create(reaction=row, species=species, coeff=coeff)
    return row


def provider_copy(species, thermo_fields=FIELDS):
    copy = db.Thermo.objects.create(species=species, **thermo_fields)
    db.ThermoRecord.objects.create(
        species=species, structure=db.Structure.objects.filter(isomer__species=species).first(),
        provider="rmg_thermo_library", external_id=f"copy-{copy.pk}", source_version="test",
        label="copy", nasa_thermo=copy)
    return copy


class MergeSplitSpeciesTests(TestCase):
    def setUp(self):
        self.single, self.full = split_records()
        self.a = db.KineticModel.objects.create(model_name="a")
        self.b = db.KineticModel.objects.create(model_name="b")
        # Model a: name and thermo on the one-form record, an empty placeholder and its
        # reaction on the full record. Model b: everything on the full record.
        db.SpeciesName.objects.create(species=self.single, kinetic_model=self.a, name="HCCO")
        db.SpeciesName.objects.create(species=self.full, kinetic_model=self.a, name="")
        db.SpeciesName.objects.create(species=self.full, kinetic_model=self.b, name="HCCO")
        self.thermo = db.Thermo.objects.create(species=self.single, **FIELDS)
        db.ThermoComment.objects.create(thermo=self.thermo, kinetic_model=self.a)
        self.record = db.ThermoRecord.objects.create(
            species=self.single, structure=db.Structure.objects.filter(isomer__species=self.single).first(),
            provider="burcat", external_id="HCCO", source_version="test", label="HCCO")
        o = get_or_create_species(None, "", [molecule("O")], MODELS)
        co = get_or_create_species(None, "", [molecule("CO")], MODELS)
        # The same reaction twice, once on each record, with the same rate.
        self.r_single = reaction((-1, self.single), (-1, o), (2, co))
        self.r_full = reaction((-1, self.full), (-1, o), (2, co))
        k_single = db.Kinetics.objects.create(reaction=self.r_single, raw_data=RATE)
        k_full = db.Kinetics.objects.create(reaction=self.r_full, raw_data=RATE)
        db.KineticsComment.objects.create(kinetics=k_single, kinetic_model=self.a)
        db.KineticsComment.objects.create(kinetics=k_full, kinetic_model=self.b)
        db.KineticsRecord.objects.create(
            reaction=self.r_full, provider="rmg_library", external_id="x", source_version="test",
            label="HCCO + O", raw_data=RATE)

    def test_report_counts_the_split(self):
        report = cleanup.integrity_report()
        self.assertEqual(report["split_species"], 1)
        self.assertEqual(report["split_species_with_model_names_on_2plus_records"], 1)
        self.assertEqual(report["name_links_empty_next_to_a_name"], 0)
        self.assertEqual(report["reactions_sharing_stoichiometry"], 0)

    def test_merge_moves_every_reference_to_the_record_with_all_forms(self):
        report = cleanup.merge_split_species(apply=True)
        self.assertEqual(report["records_merged_away"], 1)
        self.assertEqual(report["reactions_merged"], 1)
        self.assertFalse(db.Species.objects.filter(pk=self.single.pk).exists())
        full = db.Species.objects.get(pk=self.full.pk)
        self.assertEqual(full.hash, get_species_hash(full.isomers.all()))
        self.assertEqual(sorted(full.speciesname_set.values_list("kinetic_model__model_name", "name")),
                         [("a", "HCCO"), ("b", "HCCO")])
        self.thermo.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual((self.thermo.species_id, self.record.species_id), (full.pk, full.pk))
        # One reaction, one kinetics row used by both models, the provider record on it.
        reaction_row = db.Reaction.objects.get(stoichiometry__species=full)
        self.assertEqual(reaction_row.pk, self.r_single.pk)
        self.assertEqual(reaction_row.hash, cleanup.stoichiometry_hash(reaction_row.pk))
        kinetics = db.Kinetics.objects.get(reaction=reaction_row)
        self.assertEqual(set(kinetics.kineticscomment_set.values_list("kinetic_model__model_name", flat=True)),
                         {"a", "b"})
        self.assertEqual(db.KineticsRecord.objects.get().reaction_id, reaction_row.pk)
        report = cleanup.integrity_report()
        self.assertEqual((report["split_species"], report["model_names_on_2plus_records"],
                          report["species_with_stale_hash"], report["reactions_with_stale_hash"]), (0, 0, 0, 0))

    def test_dry_run_writes_nothing(self):
        before = (db.Species.objects.count(), db.Reaction.objects.count(), db.SpeciesName.objects.count())
        report = cleanup.merge_split_species(apply=False)
        self.assertEqual(report["records_merged_away"], 1)
        self.assertEqual(before, (db.Species.objects.count(), db.Reaction.objects.count(),
                                  db.SpeciesName.objects.count()))

    def test_states_are_not_merged(self):
        ground = get_or_create_species(None, "OH", [molecule("OH")], MODELS)
        excited = get_or_create_species(None, "OH*", [molecule("OH")], MODELS, electronic_state="A^2S+")
        groups = cleanup.split_groups()
        self.assertFalse(any({ground.pk, excited.pk} <= set(g) for g in groups))


class MultiKeySplitTests(TestCase):
    """CH2COOH: its resonance forms have different structure keys, so the one-form record and
    the full record do not have the same key set."""

    def test_records_sharing_one_key_are_merged(self):
        model = db.KineticModel.objects.create(model_name="a")
        single, full = split_records("CH2COOH")
        identities = cleanup.species_identities()
        self.assertLess(identities[single.pk][0], identities[full.pk][0])
        db.SpeciesName.objects.create(species=single, kinetic_model=model, name="CH2COOH")
        db.SpeciesName.objects.create(species=full, kinetic_model=model, name="CH2COOH")
        self.assertEqual(cleanup.split_groups(), [[full.pk, single.pk]])
        self.assertEqual(cleanup.integrity_report()["model_names_on_2plus_records"], 1)
        report = cleanup.merge_split_species(apply=True)
        self.assertEqual(report["records_merged_away"], 1)
        self.assertFalse(db.Species.objects.filter(pk=single.pk).exists())
        self.assertEqual(list(db.SpeciesName.objects.values_list("species_id", "name")),
                         [(full.pk, "CH2COOH")])
        report = cleanup.integrity_report()
        self.assertEqual((report["split_species"], report["model_names_on_2plus_records"],
                          report["species_with_stale_hash"]), (0, 0, 0))

    def test_one_form_records_are_joined_through_the_full_record(self):
        # Two models' thermo entries written as different forms, then a reaction with both.
        get_or_create_species(None, "", resonance_forms("CH2COOH"), MODELS)
        isomers = list(db.Isomer.objects.filter(formula__formula="C2H3O2").order_by("pk"))
        db.Species.objects.all().delete()
        one_form = []
        for isomer in isomers:
            record = db.Species.objects.create(hash=f"form {isomer.pk}")
            record.isomers.add(isomer)
            one_form.append(record.pk)
        full = db.Species.objects.create(hash="full")
        full.isomers.add(*isomers)
        # The full record is the newest, but it has the most forms.
        self.assertEqual(cleanup.split_groups(), [[full.pk, *one_form]])
        cleanup.merge_split_species(apply=True)
        self.assertEqual(list(db.Species.objects.values_list("pk", flat=True)), [full.pk])
        self.assertEqual(set(db.Species.objects.get().isomers.all()), set(isomers))

    def test_unrelated_records_stay_apart(self):
        get_or_create_species(None, "", resonance_forms("CH2COOH"), MODELS)
        get_or_create_species(None, "", [molecule("OH")], MODELS)
        get_or_create_species(None, "", [molecule("CH2CO")], MODELS)
        self.assertEqual(cleanup.split_groups(), [])


class RebuildModelLinksTests(TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.model = db.KineticModel.objects.create(model_name="model")
        self.thermo_path, self.kinetics_path = model_folder(
            self.directory, "model", ["H", "O", "O2", "OH*", "OH", "H2O", "HCCO", "CO", "AR"], kinetics=True)
        import_thermo(self.thermo_path, self.model, MODELS)
        import_kinetics(self.kinetics_path, self.model, MODELS)
        self.clean = self.links()
        self.oh = self.record("OH")
        # What an older import left: OH* also named on the ground state, a second link to one
        # thermo row, a link to a provider's copy.
        db.SpeciesName.objects.create(species=self.oh, kinetic_model=self.model, name="OH*")
        first = db.ThermoComment.objects.filter(kinetic_model=self.model).first()
        db.ThermoComment.objects.create(thermo=first.thermo, kinetic_model=self.model, comment=first.comment)
        thermo = self.oh.thermo_set.get()
        copy = provider_copy(self.oh, {k: getattr(thermo, k) for k in FIELDS})
        db.ThermoComment.objects.create(thermo=copy, kinetic_model=self.model)

    def record(self, name):
        return db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name=name,
                                      electronic_state="" if name == "OH" else "A^2S+")

    def links(self):
        return (sorted(db.SpeciesName.objects.filter(kinetic_model=self.model).values_list("species_id", "name")),
                sorted(db.ThermoComment.objects.filter(kinetic_model=self.model).values_list("thermo_id", flat=True)),
                sorted(db.KineticsComment.objects.filter(kinetic_model=self.model).values_list("kinetics_id", flat=True)))

    def test_rebuild_leaves_exactly_what_the_importer_makes(self):
        report = cleanup.integrity_report()
        self.assertEqual((report["thermo_links_duplicate"], report["thermo_links_to_provider_rows"],
                          report["excited_names_on_ground_state_records"]), (1, 1, 1))
        result = cleanup.rebuild_model_links(self.model, self.thermo_path, self.kinetics_path)
        self.assertEqual(self.links(), self.clean)
        self.assertEqual(result["names"]["removed"], 1)
        self.assertEqual(result["thermo_links"]["removed"], 2)
        self.assertEqual(result["kinetics_links"]["removed"], 0)
        report = cleanup.integrity_report()
        self.assertEqual((report["thermo_links_duplicate"], report["thermo_links_to_provider_rows"],
                          report["excited_names_on_ground_state_records"]), (0, 0, 0))

    def test_links_whose_entries_fail_to_import_are_kept(self):
        o2 = db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name="O2")
        db.SpeciesName.objects.create(species=o2, kinetic_model=self.model, name="OXYGEN")
        with open(self.kinetics_path, "w") as handle:
            handle.write("entry(\n")  # the library no longer loads
        result = cleanup.rebuild_model_links(self.model, self.thermo_path, self.kinetics_path)
        self.assertTrue(result["kinetics_import"].startswith("library not loaded"))
        names, _, kinetics = self.links()
        self.assertEqual(kinetics, self.clean[2])
        self.assertIn((o2.pk, "OXYGEN"), names)
        # A name the thermo library gives to another record is still replaced.
        self.assertNotIn((self.oh.pk, "OH*"), names)
        self.assertEqual(result["kinetics_links"]["kept_after_import_failure"], len(self.clean[2]))


class CorrectedStructureTests(TestCase):
    """A curator corrects a species' structure in the library; another entry fails to import."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        folder = os.path.join(self.directory, "model", "RMG-Py-kinetics-library")
        os.makedirs(folder)
        self.dictionary = os.path.join(folder, "dictionary.txt")
        self.reactions = os.path.join(folder, "reactions.py")
        with open(self.reactions, "w") as handle:
            handle.write('name = "test"\nshortDesc = ""\nlongDesc = """"""\nautoGenerated=False\n'
                         'entry(\n    index = 0,\n    label = "C3H5 + H <=> C3H6",\n    degeneracy = 1.0,\n'
                         "    kinetics = Arrhenius(A=(1e+14,'cm^3/(mol*s)'), n=0, Ea=(0,'cal/mol'), T0=(1,'K')),\n"
                         '    shortDesc = """test""",\n)\n')
        self.model = db.KineticModel.objects.create(model_name="model")

    def write_dictionary(self, c3h5):
        with open(self.dictionary, "w") as handle:
            for label, smiles in (("H", "[H]"), ("C3H5", c3h5), ("C3H6", "C=CC")):
                handle.write(f"{label}\n{Molecule().from_smiles(smiles).to_adjacency_list()}\n")

    def test_the_old_reaction_is_replaced_not_kept(self):
        self.write_dictionary("[CH2]C=C")  # allyl, as an older curator wrote it
        import_kinetics(self.reactions, self.model, MODELS)
        self.write_dictionary("[CH]=CC")  # corrected: 1-propenyl
        real = cleanup.import_kinetics

        def one_entry_fails(path, model, models):
            return {**real(path, model, models), "failed": 1}

        with mock.patch.object(cleanup, "import_kinetics", one_entry_fails):
            result = cleanup.rebuild_model_links(self.model, None, self.reactions)
        propenyl = Molecule().from_smiles("[CH]=CC")
        links = db.KineticsComment.objects.filter(kinetic_model=self.model)
        self.assertEqual(links.count(), 1)
        c3h5 = db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name="C3H5")
        self.assertTrue(c3h5.isomers.first().structure_set.first().to_rmg().is_isomorphic(propenyl))
        self.assertTrue(links.get().kinetics.reaction.stoichiometry_set.filter(species=c3h5).exists())
        self.assertEqual((result["kinetics_links"]["removed"], result["kinetics_links"]["kept_after_import_failure"]),
                         (1, 0))

    def test_a_record_with_two_names_is_split_and_its_old_reactions_replaced(self):
        # An older import gave C3H5 and C3H5X one record, so C3H5X <=> C3H5 became C3H5 = C3H5.
        allyl = get_or_create_species(self.model, "C3H5", [Molecule().from_smiles("[CH2]C=C")], MODELS)
        db.SpeciesName.objects.create(species=allyl, kinetic_model=self.model, name="C3H5X")
        h = get_or_create_species(self.model, "H", [Molecule().from_smiles("[H]")], MODELS)
        propene = get_or_create_species(self.model, "C3H6", [Molecule().from_smiles("C=CC")], MODELS)
        old = []
        for rows in (((-1, allyl), (-1, h), (1, propene)), ((-1, allyl), (1, allyl))):
            kinetics = db.Kinetics.objects.create(reaction=reaction(*rows), raw_data=RATE)
            db.KineticsComment.objects.create(kinetics=kinetics, kinetic_model=self.model)
            old.append(kinetics)
        # The corrected library: C3H5X is 1-propenyl.
        with open(self.dictionary, "w") as handle:
            for label, smiles in (("H", "[H]"), ("C3H5", "[CH2]C=C"), ("C3H5X", "[CH]=CC"), ("C3H6", "C=CC")):
                handle.write(f"{label}\n{Molecule().from_smiles(smiles).to_adjacency_list()}\n")
        with open(self.reactions, "a") as handle:
            handle.write('entry(\n    index = 1,\n    label = "C3H5X <=> C3H5",\n    degeneracy = 1.0,\n'
                         "    kinetics = Arrhenius(A=(1e+10,'s^-1'), n=0, Ea=(30000,'cal/mol'), T0=(1,'K')),\n"
                         '    shortDesc = """test""",\n)\n')
        real = cleanup.import_kinetics

        def one_entry_fails(path, model, models):
            return {**real(path, model, models), "failed": 1}

        with mock.patch.object(cleanup, "import_kinetics", one_entry_fails):
            result = cleanup.rebuild_model_links(self.model, None, self.reactions)
        links = db.KineticsComment.objects.filter(kinetic_model=self.model)
        self.assertEqual(links.count(), 2)
        self.assertFalse(links.filter(kinetics__in=old).exists())  # both old links were replaced
        c3h5x = db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name="C3H5X")
        self.assertNotEqual(c3h5x.pk, allyl.pk)
        self.assertEqual(result["kinetics_links"]["kept_after_import_failure"], 0)


class PruneUnlinkedRowsTests(TestCase):
    def test_only_rows_nothing_refers_to_are_deleted(self):
        model = db.KineticModel.objects.create(model_name="m")
        h = get_or_create_species(model, "H", [molecule("H")], MODELS)
        o = get_or_create_species(model, "O", [molecule("O")], MODELS)
        lonely = get_or_create_species(None, "", [molecule("AR")], MODELS)
        db.SpeciesName.objects.filter(species=lonely).delete()
        provided = get_or_create_species(None, "", [molecule("CO")], MODELS)
        db.SpeciesName.objects.filter(species=provided).delete()
        provider_copy(provided)
        used = db.Thermo.objects.create(species=h, **FIELDS)
        db.ThermoComment.objects.create(thermo=used, kinetic_model=model)
        unused = db.Thermo.objects.create(species=h, **{**FIELDS, "temp_max_2": 3000.0})
        linked = reaction((-1, h), (1, o))
        db.KineticsComment.objects.create(
            kinetics=db.Kinetics.objects.create(reaction=linked, raw_data=RATE), kinetic_model=model)
        orphan = reaction((-2, o), (1, h))
        orphan_kinetics = db.Kinetics.objects.create(reaction=orphan, raw_data=RATE)
        db.Efficiency.objects.create(species=h, kinetics=orphan_kinetics, efficiency=2.0)
        external = reaction((-1, o), (2, h))
        db.KineticsRecord.objects.create(reaction=external, provider="rmg_library", external_id="e",
                                         source_version="test", label="O = 2 H", raw_data=RATE)
        report = cleanup.prune_unlinked_rows(apply=True)
        self.assertFalse(db.Thermo.objects.filter(pk=unused.pk).exists())
        self.assertTrue(db.Thermo.objects.filter(pk=used.pk).exists())
        self.assertEqual(db.Thermo.objects.filter(species=provided).count(), 1)
        self.assertFalse(db.Kinetics.objects.filter(pk=orphan_kinetics.pk).exists())
        self.assertFalse(db.Reaction.objects.filter(pk=orphan.pk).exists())
        self.assertTrue(db.Reaction.objects.filter(pk__in=[linked.pk, external.pk]).count() == 2)
        self.assertFalse(db.Species.objects.filter(pk=lonely.pk).exists())
        self.assertTrue(db.Species.objects.filter(pk=provided.pk).exists())
        self.assertEqual(report["database.Reaction"]["kept_only_for"], {"database.KineticsRecord": 1})


class EquationTests(TestCase):
    """A kinetics link's reaction, written with its model's names, against its comment."""

    def test_the_comment_gives_both_sides(self):
        self.assertEqual(cleanup.comment_equation("The chemkin file reaction is CH2(S) + H2O <=> CH2 + H2O"),
                         [["CH2(S)", "H2O"], ["CH2", "H2O"]])
        self.assertEqual(cleanup.comment_equation("The chemkin file reaction is H + OH + M <=> H2O + M"),
                         [["H", "OH"], ["H2O"]])
        self.assertEqual(cleanup.comment_equation("The chemkin file reaction is CH3 + CH3 (+M) <=> C2H6 (+M)"),
                         [["CH3", "CH3"], ["C2H6"]])
        self.assertEqual(cleanup.comment_equation("AutoTST M062X for C5H8(1) + HO2(2) <=> C5H7(3) + H2O2(4)"),
                         [["C5H8(1)", "HO2(2)"], ["C5H7(3)", "H2O2(4)"]])
        self.assertIsNone(cleanup.comment_equation(""))
        self.assertIsNone(cleanup.comment_equation("Rate from a review"))

    def test_the_names_must_give_the_equation(self):
        singlet, triplet, water, oh, h2o2 = 1, 2, 3, 4, 5
        names = {singlet: {"CH2(S)"}, triplet: {"CH2"}, water: {"H2O"}, oh: {"OH", "OHV"}, h2o2: {"H2O2"}}
        equation = cleanup.comment_equation("The chemkin file reaction is ch2(s) + H2O <=> ch2 + H2O")
        right = [(singlet, -1), (water, -1), (triplet, 1), (water, 1)]
        self.assertTrue(cleanup.writes_equation(right, names, equation))
        self.assertTrue(cleanup.writes_equation([(s, -c) for s, c in right], names, equation))  # reverse
        # The old link: ch2(s) on the triplet record.
        self.assertFalse(cleanup.writes_equation([(triplet, -1), (water, -1), (triplet, 1), (water, 1)], names, equation))
        # 2OH is two OH; a record with two names may use either.
        self.assertTrue(cleanup.writes_equation(
            [(h2o2, -1), (oh, 2)], names, cleanup.comment_equation("The chemkin file reaction is H2O2 <=> 2OH")))
        self.assertTrue(cleanup.writes_equation(
            [(h2o2, -1), (oh, 2)], names, cleanup.comment_equation("The chemkin file reaction is H2O2 <=> OH + OHV")))
        # A name the model does not have: no verdict.
        self.assertIsNone(cleanup.writes_equation(
            right, names, cleanup.comment_equation("The chemkin file reaction is CH2X + H2O <=> CH2 + H2O")))


class MismatchedLinksTests(TestCase):
    """An older import left OH* + AR <=> OH + AR on a ground-state OH + AR = OH + AR reaction."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.model = db.KineticModel.objects.create(model_name="model")
        self.thermo_path, self.kinetics_path = model_folder(
            self.directory, "model", ["H", "O", "O2", "OH*", "OH", "H2O", "HCCO", "CO", "AR"], kinetics=True)
        import_thermo(self.thermo_path, self.model, MODELS)
        import_kinetics(self.kinetics_path, self.model, MODELS)
        self.made = set(db.KineticsComment.objects.filter(kinetic_model=self.model).values_list("pk", flat=True))
        oh = db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name="OH")
        ar = db.Species.objects.get(speciesname__kinetic_model=self.model, speciesname__name="AR")
        self.old = db.KineticsComment.objects.create(
            kinetics=db.Kinetics.objects.create(reaction=reaction((-1, oh), (-1, ar), (1, oh), (1, ar)), raw_data=RATE),
            kinetic_model=self.model, comment="The chemkin file reaction is OH* + AR <=> OH + AR")

    def test_only_the_old_link_is_found_and_deleted(self):
        self.assertEqual(cleanup.integrity_report()["kinetics_links_not_their_equation"], 1)
        rows = cleanup.prune_mismatched_links()
        self.assertEqual([k["id"] for k in rows], [self.old.pk])
        self.assertTrue(db.KineticsComment.objects.filter(pk=self.old.pk).exists())  # dry run
        cleanup.prune_mismatched_links(apply=True)
        self.assertEqual(set(db.KineticsComment.objects.filter(kinetic_model=self.model).values_list("pk", flat=True)),
                         self.made)
        self.assertEqual(cleanup.integrity_report()["kinetics_links_not_their_equation"], 0)

    def test_the_rebuild_does_not_keep_it_when_an_entry_fails(self):
        real = cleanup.import_kinetics

        def one_entry_fails(path, model, models):
            return {**real(path, model, models), "failed": 1}

        with mock.patch.object(cleanup, "import_kinetics", one_entry_fails):
            result = cleanup.rebuild_model_links(self.model, self.thermo_path, self.kinetics_path)
        links = db.KineticsComment.objects.filter(kinetic_model=self.model)
        self.assertFalse(links.filter(kinetics=self.old.kinetics).exists())
        self.assertEqual(links.count(), len(self.made))
        self.assertEqual(result["kinetics_links_not_their_equation"], 1)
