"""Append thermo-data source publication rows to ``mappings/prometheus.sssom.tsv``.

Each :class:`Thermo` record (a NASA-polynomial fit for one species) carries a
``source`` -- the publication the thermodynamic data came from. Those publications
were never minted as ``promref:`` nodes unless they happened to coincide with an
experiment or model reference, so a species had nothing to attach a "thermo data
from" provenance edge to.

This command mints the missing publication identities directly from the database:

  * ``Thermo.source.doi`` -> ``promref:<slug>``  (publication identity)

under the *same* ``promref:`` prefix as every other publication, so a thermo source
DOI that also appears as an experiment or model reference collapses to one shared
node. Grouped by DOI and idempotent twice over: skips any ``(subject, predicate,
object)`` already present and any DOI already asserted under ``promref:``.

Append-only. Import with ``import_sssom``; the ``promref`` node links to its
``Source`` via the existing DOI matcher in ``link_semantic_mappings`` (no linker
change). ``export_provenance_edges`` then draws ``species --thermo data from-->
publication`` edges.
"""

import csv
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models.thermo_transport import Thermo

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_thermo_source_sssom"


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
        "Append promref: SSSOM rows for thermo-data source publications "
        "(Thermo.source) to prometheus.sssom.tsv (idempotent)."
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
        for th in (
            Thermo.objects.filter(source__isnull=False).select_related("source")
        ):
            doi = _norm_doi(th.source.doi)
            if not doi or doi.lower() in promref_dois or doi in ref_rows:
                continue
            label = _source_label(th.source)
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
                    "thermo.source.doi", "1.0", TOOL, today, AUTHOR_ID,
                    "Publication identity asserted from the thermo data's source DOI.",
                ]
            )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new thermo-source DOI rows -- all already covered.")
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
