import io

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from database.models import Formula, Isomer, Species, Structure
from database.services.chemical_identity import inchikey_of, inchikey_species_map
from provenance.models import ExternalIdentifier, IdentifierScheme

METHANE_KEY = "VNWKTOKETHGBQD-UHFFFAOYSA-N"
METHANE_INCHI = "InChI=1S/CH4/h1H4"


class InchikeyOfTests(SimpleTestCase):
    def test_strips_the_multiplicity(self):
        self.assertEqual(inchikey_of(f"{METHANE_KEY}-1"), METHANE_KEY)
        self.assertEqual(inchikey_of(f"{METHANE_KEY}-3"), METHANE_KEY)

    def test_empty_keys(self):
        self.assertEqual(inchikey_of(""), "")
        self.assertEqual(inchikey_of("-2"), "")


class StructureIdentifierTests(TestCase):
    """Structure fields are the source of truth for species identifiers."""

    @classmethod
    def setUpTestData(cls):
        formula, _ = Formula.objects.get_or_create(formula="CH4")
        isomer = Isomer.objects.create(formula=formula, inchi=METHANE_INCHI)
        cls.species = Species.objects.create(hash="methane", cas_number="74-82-8")
        cls.species.isomers.add(isomer)
        structure = Structure.objects.create(
            isomer=isomer, smiles="C", adjacency_list="methane fixture", multiplicity=1,
        )
        # save() derives structure_key from the adjacency list, which a fixture cannot do.
        Structure.objects.filter(pk=structure.pk).update(
            structure_key=f"{METHANE_KEY}-1", pubchem_cid=297,
        )
        cls.content_type = ContentType.objects.get_for_model(Species)

    def identifiers(self):
        return set(
            ExternalIdentifier.objects.filter(
                content_type=self.content_type, object_id=self.species.pk
            ).values_list("scheme", "value", "is_primary")
        )

    def test_species_inchikey_comes_from_the_structure(self):
        self.assertEqual(self.species.inchikey, METHANE_KEY)

    def test_inchikey_species_map(self):
        self.assertEqual(inchikey_species_map(), {METHANE_KEY: self.species.pk})

    def test_populate_mirrors_structure_fields_and_removes_stale_rows(self):
        ExternalIdentifier.objects.create(
            content_type=self.content_type, object_id=self.species.pk,
            scheme=IdentifierScheme.INCHIKEY, value="STALESTALESTAL-UHFFFAOYSA-N", is_primary=True,
        )
        expected = {
            ("inchikey", METHANE_KEY, True),
            ("pubchem.compound", "297", False),
            ("smiles", "C", False),
            ("inchi", METHANE_INCHI, False),
            ("cas", "74-82-8", False),
        }
        call_command("populate_species_identifiers", stdout=io.StringIO())
        self.assertEqual(self.identifiers(), expected)
        # Running it again changes nothing.
        call_command("populate_species_identifiers", stdout=io.StringIO())
        self.assertEqual(self.identifiers(), expected)
