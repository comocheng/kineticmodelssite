"""Append ChemKED dataset DOI rows to ``mappings/prometheus.sssom.tsv``.

The original ``generate_sssom.py`` emitted a ``promref:`` row only for references
it happened to parse out of curated YAML, so most ExperimentDataset DOIs never got
a mapping row. This command closes that in-house gap directly from the database:

  * ``ExperimentDataset.reference_doi`` -> ``promref:<slug>`` (publication identity)
  * ``ExperimentDataset.file_doi``      -> ``promds:<slug>``  (dataset identity)

Both are ``skos:exactMatch`` to ``doi:<id>``. Rows are grouped by DOI so each
publication/dataset gets exactly one subject, and the command is idempotent twice
over: it skips any ``(subject, predicate, object)`` already in the TSV *and* any DOI
already asserted under the same prefix (so re-running never mints a rival subject
for a DOI that ``generate_sssom.py`` already covered).

Append-only (no header rewrite). Import with ``import_sssom`` then attach foreign
keys with ``link_semantic_mappings`` (its DOI matcher links both prefixes to the
ExperimentDataset automatically -- no linker change needed).
"""

import csv
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from chemked_database.models import ExperimentDataset

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_dataset_doi_sssom"

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


def _norm_doi(value):
    value = (value or "").strip()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)


def _surname(author_name):
    """`'T Asaba'` -> `'Asaba'`; best-effort last token."""
    parts = (author_name or "").strip().split()
    return parts[-1] if parts else ""


def _reference_label(authors, year, journal):
    names = [a for a in authors if a]
    if names:
        lead = _surname(names[0]) or names[0]
        who = f"{lead} et al." if len(names) > 1 else lead
    else:
        who = "Unknown"
    bits = [who]
    if year:
        bits.append(str(year))
    label = " ".join(bits)
    if journal:
        label = f"{label}, {journal}"
    return label


class Command(BaseCommand):
    help = (
        "Append promref: (reference_doi) and promds: (file_doi) SSSOM rows for "
        "ExperimentDatasets to prometheus.sssom.tsv (idempotent)."
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

        # Idempotency: exact triple keys + DOIs already asserted per prefix.
        existing_keys = set()
        promref_dois = set()
        promds_dois = set()
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                subj = row.get("subject_id") or ""
                obj = row.get("object_id") or ""
                existing_keys.add((subj, row.get("predicate_id"), obj))
                if obj.startswith("doi:"):
                    doi = _norm_doi(obj[len("doi:"):]).lower()
                    if subj.startswith("promref:"):
                        promref_dois.add(doi)
                    elif subj.startswith("promds:"):
                        promds_dois.add(doi)

        today = date.today().isoformat()

        # Group by DOI so each publication/dataset yields one subject.
        ref_rows = OrderedDict()  # doi -> [subject, label]
        ds_rows = OrderedDict()
        for ds in ExperimentDataset.objects.prefetch_related("reference_authors"):
            ref_doi = _norm_doi(ds.reference_doi)
            if ref_doi and ref_doi.lower() not in promref_dois and ref_doi not in ref_rows:
                authors = list(ds.reference_authors.values_list("name", flat=True))
                label = _reference_label(authors, ds.reference_year, ds.reference_journal)
                subject = f"promref:{_slug(label)}" if _slug(label) else f"promref:{_slug(ref_doi)}"
                ref_rows[ref_doi] = [subject, label]

            file_doi = _norm_doi(ds.file_doi)
            if file_doi and file_doi.lower() not in promds_dois and file_doi not in ds_rows:
                local = file_doi.split("/")[-1] or file_doi
                subject = f"promds:{_slug(local)}"
                label = ds.chemked_file_path or file_doi
                ds_rows[file_doi] = [subject, label]

        new_rows = []
        for doi, (subject, label) in ref_rows.items():
            key = (subject, PREDICATE, f"doi:{doi}")
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_rows.append(
                [
                    subject, label, PREDICATE, f"doi:{doi}", label, JUSTIFICATION,
                    "experiment-dataset.reference_doi", "1.0", TOOL, today, AUTHOR_ID,
                    "Publication identity asserted from the reference DOI in the dataset.",
                ]
            )
        ref_count = len(new_rows)
        for doi, (subject, label) in ds_rows.items():
            key = (subject, PREDICATE, f"doi:{doi}")
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_rows.append(
                [
                    subject, label, PREDICATE, f"doi:{doi}", label, JUSTIFICATION,
                    "experiment-dataset.file_doi", "1.0", TOOL, today, AUTHOR_ID,
                    "Dataset identity asserted from the ReSpecTh/file DOI.",
                ]
            )
        ds_count = len(new_rows) - ref_count

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new dataset DOI rows -- all already covered.")
            )
            return

        if options["dry_run"]:
            for r in new_rows:
                self.stdout.write("\t".join(r))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[dry-run] {len(new_rows)} rows would be appended "
                    f"(promref {ref_count}, promds {ds_count})."
                )
            )
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Appended {len(new_rows)} rows to {path.name} "
                f"(promref {ref_count}, promds {ds_count})."
            )
        )
