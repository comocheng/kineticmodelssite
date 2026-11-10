"""Append kinetic-model source publication rows to ``mappings/prometheus.sssom.tsv``.

The SSSOM set already mints ``promref:`` publication nodes for ChemKED *experiment*
references (via ``generate_sssom.py`` / ``generate_dataset_doi_sssom.py``), but the
publications that kinetic *models* were built from -- ``KineticModel.source`` -- were
never minted, so the model nodes had nothing to attach a "derived from" edge to.
These are a disjoint body of literature (mechanism/model papers, not experiment
reports), which is exactly why a model's source DOI never matched an experiment
``promref`` DOI.

This command closes that gap directly from the database:

  * ``KineticModel.source.doi`` -> ``promref:<slug>`` (publication identity)

minted as ``skos:exactMatch`` to ``doi:<id>`` under the *same* ``promref:`` prefix
as experiment references -- a publication is a publication, so if a model source DOI
ever coincides with an experiment reference DOI they collapse to one shared node.
Grouped by DOI (one subject per publication) and idempotent twice over: it skips any
``(subject, predicate, object)`` already present *and* any DOI already asserted under
``promref:`` (so it never mints a rival subject for a DOI an experiment generator
already covered).

Append-only (no header rewrite). Import with ``import_sssom`` then attach foreign
keys with ``link_semantic_mappings`` (its DOI matcher links the ``promref`` node to
the ``Source`` carrying that DOI -- no linker change needed). The provenance overlay
``export_provenance_edges`` then resolves the model's ``from`` edge automatically.
"""

import csv
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models import KineticModel

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_model_source_sssom"

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


def _source_label(source):
    """Build a human label like ``'Smith et al. 2014, Combustion and Flame'``."""
    authors = list(source.authorship_set.order_by("order").select_related("author"))
    if authors:
        lead = authors[0].author.lastname or str(authors[0].author)
        who = f"{lead} et al." if len(authors) > 1 else lead
    else:
        who = source.source_title or "Unknown"
    bits = [who]
    if source.publication_year:
        bits.append(str(source.publication_year))
    label = " ".join(bits)
    if source.journal_name:
        label = f"{label}, {source.journal_name}"
    return label


class Command(BaseCommand):
    help = (
        "Append promref: SSSOM rows for kinetic-model source publications "
        "(KineticModel.source) to prometheus.sssom.tsv (idempotent)."
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

        # Idempotency: exact triple keys + DOIs already asserted under promref:.
        existing_keys = set()
        promref_dois = set()
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                subj = row.get("subject_id") or ""
                obj = row.get("object_id") or ""
                existing_keys.add((subj, row.get("predicate_id"), obj))
                if subj.startswith("promref:") and obj.startswith("doi:"):
                    promref_dois.add(_norm_doi(obj[len("doi:"):]).lower())

        today = date.today().isoformat()

        # Group by DOI so each model-source publication yields one subject.
        ref_rows = OrderedDict()  # doi -> [subject, label]
        for km in (
            KineticModel.objects.filter(source__isnull=False)
            .select_related("source")
        ):
            doi = _norm_doi(km.source.doi)
            if not doi or doi.lower() in promref_dois or doi in ref_rows:
                continue
            label = _source_label(km.source)
            subject = (
                f"promref:{_slug(label)}" if _slug(label) else f"promref:{_slug(doi)}"
            )
            ref_rows[doi] = [subject, label]

        new_rows = []
        for doi, (subject, label) in ref_rows.items():
            key = (subject, PREDICATE, f"doi:{doi}")
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_rows.append(
                [
                    subject, label, PREDICATE, f"doi:{doi}", label, JUSTIFICATION,
                    "kinetic-model.source.doi", "1.0", TOOL, today, AUTHOR_ID,
                    "Publication identity asserted from the kinetic model's source DOI.",
                ]
            )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new model-source DOI rows -- all already covered.")
            )
            return

        if options["dry_run"]:
            for r in new_rows:
                self.stdout.write("\t".join(r))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[dry-run] {len(new_rows)} promref rows would be appended."
                )
            )
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Appended {len(new_rows)} promref rows to {path.name}."
            )
        )
