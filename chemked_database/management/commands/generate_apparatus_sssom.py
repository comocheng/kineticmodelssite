"""Append experimental-apparatus identity rows to ``mappings/prometheus.sssom.tsv``.

The apparatus *institutions* are already minted as ``promorg:`` nodes (with a
``ror:`` cross-reference) by ``generate_sssom.py``, but the apparatus *instances*
themselves -- the Stanford shock tube, the NUI Galway RCM, ... referenced by
``ExperimentDataset.apparatus`` -- had no node, so a dataset had nothing to attach
a "produced with this apparatus" edge to, and an apparatus had nothing to attach a
"located at this institution" edge to.

This command mints one ``promapp:<slug>`` node per :class:`Apparatus`, anchored to
its ontology *type* (``pmtx:Apparatus``) with ``skos:broadMatch`` -- the generic
class is broader than the specific instance, so this is a type assertion, not an
identity claim against an external registry (apparatus instances have no such
registry). The minted node becomes a graph subject; ``link_semantic_mappings``
then attaches the ``Apparatus`` foreign key (matching on ``Apparatus.sssom_slug``),
and ``export_provenance_edges`` resolves the ``located at institution`` and
``uses apparatus`` edges automatically.

Append-only (no header rewrite) and idempotent: skips any ``(subject, predicate,
object)`` already present. Run, then ``import_sssom`` and ``link_semantic_mappings``.
"""

import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from chemked_database.models import Apparatus

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:broadMatch"
OBJECT = "pmtx:Apparatus"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_apparatus_sssom"


class Command(BaseCommand):
    help = (
        "Append promapp: SSSOM rows for experimental apparatus instances "
        "to prometheus.sssom.tsv (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT))
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the rows that would be appended without writing the file.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"SSSOM file not found: {path}"))
            return

        existing_keys = set()
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                existing_keys.add(
                    (
                        row.get("subject_id") or "",
                        row.get("predicate_id"),
                        row.get("object_id") or "",
                    )
                )

        today = date.today().isoformat()

        seen_subjects = set()
        new_rows = []
        for ap in Apparatus.objects.select_related("institution_ref").all():
            slug = ap.sssom_slug
            if not slug or slug in seen_subjects:
                continue
            seen_subjects.add(slug)
            subject = f"promapp:{slug}"
            key = (subject, PREDICATE, OBJECT)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_rows.append(
                [
                    subject, str(ap), PREDICATE, OBJECT, "Experimental Apparatus",
                    JUSTIFICATION, "apparatus.kind-institution-facility", "1.0", TOOL,
                    today, AUTHOR_ID,
                    "Apparatus instance typed against the pmtx:Apparatus class.",
                ]
            )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new apparatus rows -- all already covered.")
            )
            return

        if options["dry_run"]:
            for r in new_rows:
                self.stdout.write("\t".join(r))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[dry-run] {len(new_rows)} promapp rows would be appended."
                )
            )
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Appended {len(new_rows)} promapp rows to {path.name}."
            )
        )
