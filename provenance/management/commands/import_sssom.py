import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from provenance.models import SemanticMapping

# The SSSOM file lives at the workspace root (one level above the Django
# project), at Prometheus/mappings/prometheus.sssom.tsv.
DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
SET_ID = "https://dev.omethe.us/mappings/prometheus.sssom.tsv"


class Command(BaseCommand):
    help = "Import SSSOM rows from a .sssom.tsv file into SemanticMapping (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT))

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"SSSOM file not found: {path}"))
            return

        created = updated = 0
        with path.open(newline="", encoding="utf-8") as fh:
            rows = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(rows, delimiter="\t"):
                if not row.get("subject_id") or not row.get("object_id"):
                    continue
                md = (row.get("mapping_date") or "").strip()
                _, made = SemanticMapping.objects.update_or_create(
                    subject_id=row["subject_id"],
                    predicate_id=row.get("predicate_id") or "skos:exactMatch",
                    object_id=row["object_id"],
                    defaults={
                        "mapping_set_id": SET_ID,
                        "subject_label": row.get("subject_label", ""),
                        "object_label": row.get("object_label", ""),
                        "mapping_justification": row.get("mapping_justification", ""),
                        "subject_match_field": row.get("subject_match_field", ""),
                        "confidence": float(row.get("confidence") or 1.0),
                        "mapping_tool": row.get("mapping_tool", ""),
                        "mapping_date": date.fromisoformat(md) if md else None,
                        "author_id": row.get("author_id", ""),
                        "comment": row.get("comment", ""),
                    },
                )
                created += int(made)
                updated += int(not made)
        self.stdout.write(self.style.SUCCESS(f"SSSOM import: {created} created, {updated} updated."))
