"""Apply the checked institutions (provenance.institution_curation) to the database and to the SSSOM
file: merge the other spellings of an institution into one record, link each lab or department
to its parent, give each record its own ROR id, and correct the ROR mappings (the lexical match
named seven other organisations). A dry run by default; --apply writes.

    python manage.py curate_institutions                  # dry run
    python manage.py curate_institutions --apply
    python manage.py curate_institutions --apply --tsv ../mappings/sssom/prometheus.sssom.tsv

Run it after generate_sssom.py and import_sssom, which make the mappings from the free text of
the ChemKED files again.
"""
import csv
import io
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from provenance import institution_curation as curation
from provenance.models import Institution, SemanticMapping

TOOL = "provenance.institution_curation"
COMMENT = f"Checked against the ROR registry on {curation.CHECKED}."
NO_ROR = f"ROR has no record of this organisation (checked {curation.CHECKED})."
DEFAULT_TSV = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"


def wanted_mapping(label):
    """The (predicate, object_id, object_label, comment) of the ROR row of ``label``, or None."""
    mapping = curation.ror_mapping(label)
    if mapping is None:
        return None
    ror, predicate = mapping
    if not ror:
        return "skos:broadMatch", "(unresolved)", "", NO_ROR
    return predicate, f"ror:{ror}", curation.ROR_NAMES.get(ror, ""), COMMENT


def is_ror_row(object_id):
    return object_id.startswith("ror:") or object_id == "(unresolved)"


def merge(duplicate, target, log):
    """Point everything at ``target`` instead of ``duplicate``, then delete ``duplicate``."""
    for relation in Institution._meta.related_objects:
        if relation.one_to_many or relation.one_to_one:
            moved = relation.related_model.objects.filter(**{relation.field.name: duplicate}).update(
                **{relation.field.name: target})
            if moved:
                log(f"    {moved} {relation.related_model._meta.verbose_name_plural} moved")
    duplicate.delete()


class Command(BaseCommand):
    help = "Merge, link and correct the institutions from the checked list (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes.")
        parser.add_argument("--tsv", default=str(DEFAULT_TSV),
                            help="SSSOM file to correct as well (skipped when it does not exist).")

    def handle(self, *args, **options):
        apply = options["apply"]
        self.stdout.write("Writing the changes." if apply else "Dry run: nothing is written (use --apply).")
        with transaction.atomic():
            self.institutions()
            self.mappings()
            if not apply:
                transaction.set_rollback(True)
        self.tsv(Path(options["tsv"]), apply)

    def institutions(self):
        log = self.stdout.write
        log("Institutions:")
        created, merged, linked, ror_changed = [], 0, 0, 0
        for name, entry in curation.INSTITUTIONS.items():
            if "same_as" not in entry:
                continue
            for duplicate in Institution.objects.filter(name=name):
                target = curation.institution_for(name, created)
                log(f"  merge '{name}' into '{target.name}'")
                merge(duplicate, target, log)
                merged += 1
        for institution in Institution.objects.filter(name__in=list(curation.INSTITUTIONS)):
            parent_name = curation.parent_of(institution.name)
            parent = curation.institution_for(parent_name, created) if parent_name else None
            ror = curation.own_ror(institution.name)
            changes = []
            if institution.parent_id != (parent.pk if parent else None):
                institution.parent = parent
                changes.append(f"part of '{parent.name}'" if parent else "no parent")
                linked += 1
            if institution.ror_id != ror:
                changes.append(f"ROR {institution.ror_id or '-'} -> {ror or '-'}")
                institution.ror_id = ror
                ror_changed += 1
            if changes:
                institution.save(update_fields=["parent", "ror_id"])
                log(f"  {institution.name}: " + "; ".join(changes))
        for name in created:
            log(f"  new record: {name}")
        log(f"  {len(created)} new, {merged} merged, {linked} linked to a parent, {ror_changed} ROR ids changed")

    def mappings(self):
        log = self.stdout.write
        log("ROR mappings in the database:")
        changed = removed = 0
        for row in SemanticMapping.objects.filter(subject_label__in=list(curation.INSTITUTIONS)).order_by("pk"):
            if not is_ror_row(row.object_id):
                continue
            predicate, object_id, object_label, comment = wanted_mapping(row.subject_label)
            same = (row.predicate_id, row.object_id, row.mapping_tool) == (predicate, object_id, TOOL)
            if same:
                continue
            if row.object_id != object_id:
                log(f"  {row.subject_label}: {row.object_id} -> {object_id}")
            duplicate = (SemanticMapping.objects.filter(subject_id=row.subject_id, predicate_id=predicate,
                                                        object_id=object_id).exclude(pk=row.pk).exists())
            if duplicate:
                row.delete()
                removed += 1
                continue
            row.predicate_id, row.object_id, row.object_label, row.comment = predicate, object_id, object_label, comment
            row.mapping_justification, row.mapping_tool, row.confidence = "semapv:ManualMappingCuration", TOOL, 1.0
            row.mapping_date = date.fromisoformat(curation.CHECKED)
            row.save()
            changed += 1
        log(f"  {changed} rows corrected or marked as checked, {removed} duplicate rows removed")

    def tsv(self, path, apply):
        log = self.stdout.write
        if not path.exists():
            log(f"SSSOM file: {path} not found, skipped.")
            return
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        header_at = next(i for i, line in enumerate(lines) if line.startswith("subject_id\t"))
        columns = lines[header_at].rstrip("\n").split("\t")
        at = {name: columns.index(name) for name in columns}
        changed = 0
        for i in range(header_at + 1, len(lines)):
            if lines[i].startswith("#") or not lines[i].strip():
                continue
            cells = next(csv.reader([lines[i].rstrip("\n")], delimiter="\t", quoting=csv.QUOTE_NONE))
            if cells[at["subject_label"]] not in curation.INSTITUTIONS or not is_ror_row(cells[at["object_id"]]):
                continue
            predicate, object_id, object_label, comment = wanted_mapping(cells[at["subject_label"]])
            new = dict(predicate_id=predicate, object_id=object_id, object_label=object_label, comment=comment,
                       mapping_justification="semapv:ManualMappingCuration", confidence="1.0",
                       mapping_tool=TOOL, mapping_date=curation.CHECKED)
            if all(cells[at[key]] == value for key, value in new.items()):
                continue
            if cells[at["object_id"]] != object_id:
                log(f"  file: {cells[at['subject_label']]}: {cells[at['object_id']]} -> {object_id}")
            for key, value in new.items():
                cells[at[key]] = value
            out = io.StringIO()
            csv.writer(out, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\", lineterminator="\n").writerow(cells)
            lines[i] = out.getvalue()
            changed += 1
        log(f"SSSOM file {path.name}: {changed} rows corrected or marked as checked"
            + ("" if apply else " (not written)"))
        if apply and changed:
            path.write_text("".join(lines), encoding="utf-8")
