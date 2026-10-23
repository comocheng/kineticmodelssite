"""Append kinetic-model SSSOM rows to ``mappings/prometheus.sssom.tsv``.

``generate_sssom.py`` only reads ChemKED experiment YAML, so it emits species,
reference, agent, and institution mappings -- it has no notion of a kinetic
model. This command is the kinetic-model counterpart: it reads
``database.KineticModel`` rows and emits ``promkm:`` mapping rows that cross-
reference each model to its external authority:

  * ``zenodo_doi``     -> ``doi:<id>``
  * ``prime_id``       -> ``prime:<id>``
  * ``repository_url`` -> the repository IRI

Rows are appended to the shared SSSOM TSV (no header rewrite) and the command is
idempotent: an existing ``(subject_id, predicate_id, object_id)`` is never
duplicated. Import the result with ``import_sssom`` and attach the foreign keys
with ``link_semantic_mappings``.
"""

import csv
import re
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models import KineticModel

# Same location import_sssom reads from: Prometheus/mappings/prometheus.sssom.tsv.
DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"

COLUMNS = [
    "subject_id",
    "subject_label",
    "predicate_id",
    "object_id",
    "object_label",
    "mapping_justification",
    "subject_match_field",
    "confidence",
    "mapping_tool",
    "mapping_date",
    "author_id",
    "comment",
]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _strip_doi(value):
    value = (value or "").strip()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)


class Command(BaseCommand):
    help = "Append kinetic-model SSSOM rows (DOI/PrIMe/repository) to prometheus.sssom.tsv (idempotent)."

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

        existing = set()
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                existing.add(
                    (row.get("subject_id"), row.get("predicate_id"), row.get("object_id"))
                )

        today = date.today().isoformat()
        new_rows = []
        for km in KineticModel.objects.all():
            subject = f"promkm:{_slug(km.model_name)}"
            label = km.model_name
            targets = []
            if (km.zenodo_doi or "").strip():
                targets.append(
                    (
                        f"doi:{_strip_doi(km.zenodo_doi)}",
                        "kinetic-model.zenodo_doi",
                        "Model identity asserted from the Zenodo DOI.",
                    )
                )
            if (km.prime_id or "").strip():
                targets.append(
                    (
                        f"prime:{km.prime_id.strip()}",
                        "kinetic-model.prime_id",
                        "Model cross-referenced to its PrIMe record.",
                    )
                )
            if (km.repository_url or "").strip():
                targets.append(
                    (
                        km.repository_url.strip(),
                        "kinetic-model.repository_url",
                        "Model source repository.",
                    )
                )
            for object_id, match_field, comment in targets:
                key = (subject, PREDICATE, object_id)
                if key in existing:
                    continue
                existing.add(key)
                new_rows.append(
                    [
                        subject,
                        label,
                        PREDICATE,
                        object_id,
                        label,
                        "semapv:UnspecifiedMatching",
                        match_field,
                        "1.0",
                        "generate_model_sssom",
                        today,
                        AUTHOR_ID,
                        comment,
                    ]
                )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING(
                    "No new kinetic-model rows. "
                    "KineticModel.zenodo_doi / prime_id / repository_url are all empty -- "
                    "populate those fields first."
                )
            )
            return

        if options["dry_run"]:
            for r in new_rows:
                self.stdout.write("\t".join(r))
            self.stdout.write(
                self.style.SUCCESS(f"[dry-run] {len(new_rows)} kinetic-model rows would be appended.")
            )
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Appended {len(new_rows)} kinetic-model rows to {path.name}."
            )
        )
