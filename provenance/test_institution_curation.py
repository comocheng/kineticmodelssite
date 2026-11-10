"""The checked institutions: merged spellings, parents, own ROR ids, and corrected ROR mappings in the
database and in the SSSOM file."""
import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from chemked_database.models import Apparatus
from provenance import institution_curation as curation
from provenance.models import Institution, SemanticMapping

HTGL = "High Temperature Gasdynamics Laboratory, Department of Mechanical Engineering, Stanford University"
HTGL_SHORT = "High Temperature Gasdynamics Laboratory, Stanford University"
HEADER = ("subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\t"
          "subject_match_field\tconfidence\tmapping_tool\tmapping_date\tauthor_id\tcomment\n")


def tsv_row(slug, label, object_id):
    return (f"promorg:{slug}\t{label}\tskos:broadMatch\t{object_id}\t\tsemapv:LexicalMatching\t"
            f"apparatus.institution\t0.8\tgenerate_sssom.py (ROR)\t2026-06-10\torcid:0000\tVERIFY.\n")


class CurationTableTests(TestCase):
    def test_every_reference_is_in_the_table(self):
        for name, entry in curation.INSTITUTIONS.items():
            for other in (entry.get("same_as"), entry.get("parent")):
                if other:
                    self.assertIn(other, curation.INSTITUTIONS, name)
            if entry.get("ror"):
                self.assertIn(entry["ror"], curation.ROR_NAMES, name)

    def test_lab_maps_broadly_to_the_university(self):
        self.assertEqual(curation.ror_mapping(HTGL_SHORT), ("00f54p054", "skos:broadMatch"))
        self.assertEqual(curation.ror_mapping("Stanford University"), ("00f54p054", "skos:exactMatch"))
        self.assertEqual(curation.ror_mapping("Aachen University"), ("04xfq0f34", "skos:exactMatch"))
        self.assertEqual(curation.ror_mapping("United Technologies Research Center"), ("", ""))
        self.assertIsNone(curation.ror_mapping("Not in the table"))


class CurateInstitutionsTests(TestCase):
    def setUp(self):
        self.stanford = Institution.objects.create(name="Stanford University", ror_id="00f54p054")
        self.me = Institution.objects.create(name="Department of Mechanical Engineering, Stanford University",
                                             ror_id="00f54p054")
        self.htgl = Institution.objects.create(name=HTGL, ror_id="04q2cht42")
        self.htgl_short = Institution.objects.create(name=HTGL_SHORT, ror_id="04q2cht42")
        self.sloan = Institution.objects.create(name="Sloan Automotive Laboratory, M.I.T.", ror_id="01hbh1z68")
        self.other = Institution.objects.create(name="Somewhere Else", ror_id="0abcdef12")
        self.apparatus = Apparatus.objects.create(kind="shock tube", institution=HTGL_SHORT,
                                                  institution_ref=self.htgl_short)
        for label, ror in ((HTGL_SHORT, "ror:04q2cht42"), ("Stanford University", "ror:00f54p054"),
                           ("United Technologies Research Center", "ror:04vxc1c96")):
            SemanticMapping.objects.create(subject_id=f"promorg:{label[:20]}", subject_label=label,
                                           predicate_id="skos:broadMatch", object_id=ror)
        self.file = Path(tempfile.mkdtemp()) / "prometheus.sssom.tsv"
        self.file.write_text("# comment\n" + HEADER
                             + tsv_row("htgl", HTGL_SHORT, "ror:04q2cht42")
                             + tsv_row("aachen", "Aachen University", "ror:02gm5zw39")
                             + tsv_row("other", "Somewhere Else", "ror:0abcdef12"), encoding="utf-8")

    def run_command(self, *args):
        out = io.StringIO()
        call_command("curate_institutions", "--tsv", str(self.file), *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        before = self.file.read_text()
        self.run_command()
        self.assertEqual(Institution.objects.count(), 6)
        self.assertEqual(self.file.read_text(), before)
        self.assertTrue(SemanticMapping.objects.filter(object_id="ror:04q2cht42").exists())

    def test_apply_merges_links_and_corrects(self):
        self.run_command("--apply")
        self.assertFalse(Institution.objects.filter(name=HTGL_SHORT).exists())
        self.apparatus.refresh_from_db()
        self.assertEqual(self.apparatus.institution_ref, self.htgl)
        self.htgl.refresh_from_db()
        self.assertEqual((self.htgl.parent, self.htgl.ror_id), (self.me, ""))
        self.me.refresh_from_db()
        self.assertEqual((self.me.parent, self.me.ror_id), (self.stanford, ""))
        mit = Institution.objects.get(name="Massachusetts Institute of Technology")
        self.sloan.refresh_from_db()
        self.assertEqual((self.sloan.parent, self.sloan.ror_id, mit.ror_id), (mit, "", "042nb2s44"))
        self.other.refresh_from_db()
        self.assertEqual(self.other.ror_id, "0abcdef12")      # not in the table: unchanged

        lab = SemanticMapping.objects.get(subject_label=HTGL_SHORT)
        self.assertEqual((lab.predicate_id, lab.object_id), ("skos:broadMatch", "ror:00f54p054"))
        self.assertEqual(lab.mapping_justification, "semapv:ManualMappingCuration")
        own = SemanticMapping.objects.get(subject_label="Stanford University")
        self.assertEqual(own.predicate_id, "skos:exactMatch")
        utrc = SemanticMapping.objects.get(subject_label="United Technologies Research Center")
        self.assertEqual(utrc.object_id, "(unresolved)")

        text = self.file.read_text()
        self.assertNotIn("04q2cht42", text)
        self.assertNotIn("02gm5zw39", text)
        self.assertIn("ror:0abcdef12", text)
        self.assertIn("\tskos:exactMatch\tror:04xfq0f34\tRWTH Aachen University\tsemapv:ManualMappingCuration", text)

    def test_second_run_changes_nothing(self):
        self.run_command("--apply")
        out = self.run_command("--apply")
        self.assertIn("0 new, 0 merged, 0 linked to a parent, 0 ROR ids changed", out)
        self.assertIn("0 rows corrected or marked as checked, 0 duplicate rows removed", out)
        self.assertIn("prometheus.sssom.tsv: 0 rows", out)

    def test_backfill_uses_the_table(self):
        Apparatus.objects.create(kind="shock tube", institution="Rensselaer Polytechnic Institution")
        call_command("backfill_identity", stdout=io.StringIO())
        rpi = Institution.objects.get(name="Rensselaer Polytechnic Institute")
        self.assertEqual(rpi.ror_id, "01rtyzb94")
        self.assertFalse(Institution.objects.filter(name="Rensselaer Polytechnic Institution").exists())
        self.assertEqual(Apparatus.objects.get(institution="Rensselaer Polytechnic Institution").institution_ref, rpi)
