"""Append kinetics-data source publication rows to ``mappings/prometheus.sssom.tsv``.

Each :class:`Kinetics` record (a rate expression for one reaction) carries a
``source`` -- the publication the rate data came from. A kinetic model aggregates
many such rate records (``KineticModel.kinetics``), so a model's mechanism draws on
a body of underlying rate-measurement papers distinct from the single model paper
already minted by ``generate_model_source_sssom``. Those rate-source publications
were never minted, so a model had nothing to attach "kinetics data from" edges to.

This command mints the missing publication identities directly from the database:

  * ``Kinetics.source.doi`` -> ``promref:<slug>``  (publication identity)

under the shared ``promref:`` prefix (so a rate source DOI that coincides with any
other reference collapses to one node). Grouped by DOI and idempotent twice over:
skips any ``(subject, predicate, object)`` already present and any DOI already
asserted under ``promref:``.

Append-only. Import with ``import_sssom``; the ``promref`` node links to its
``Source`` via the existing DOI matcher in ``link_semantic_mappings`` (no linker
change). ``export_provenance_edges`` then draws ``kinetic model --kinetics data
from--> publication`` edges.
"""

import csv
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models.kinetic_data import Kinetics

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_kinetics_source_sssom"


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
        "Append promref: SSSOM rows for kinetics-data source publications "
        "(Kinetics.source) to prometheus.sssom.tsv (idempotent)."
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

        ref_rows = OrderedDict()  # doi -> [subject, label]
        for kin in (
            Kinetics.objects.filter(source__isnull=False).select_related("source")
        ):
            doi = _norm_doi(kin.source.doi)
            if not doi or doi.lower() in promref_dois or doi in ref_rows:
                continue
            label = _source_label(kin.source)
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
                    "kinetics.source.doi", "1.0", TOOL, today, AUTHOR_ID,
                    "Publication identity asserted from the kinetics data's source DOI.",
                ]
            )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new kinetics-source DOI rows -- all already covered.")
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
