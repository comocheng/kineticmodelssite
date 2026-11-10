"""Backfill ``Thermo.source`` / ``Kinetics.source`` from the kinetic model's source.

Imported thermo and kinetics records carry no ``source`` of their own (the RMG
import never set it), so a species' thermodynamic fit and a reaction's rate
expression have no publication attached -- the ``thermoFrom`` / ``kineticsFrom``
provenance edges therefore resolve to nothing.

The pragmatic, honest fill is the *model's* source publication: a thermo/kinetics
record used by kinetic model M is, at minimum, attributable to the paper that
describes M. This command sets that link -- but only when it is **unambiguous**.

A single record is frequently shared across several models (it is an M2M through
``ThermoComment`` / ``KineticsComment``), and those models can cite *different*
papers. ``Thermo.source`` / ``Kinetics.source`` is a single foreign key, so when
the using models disagree there is no honest single answer:

  * exactly one distinct model-source  -> set the foreign key.
  * two or more distinct model-sources -> left NULL (reported as ambiguous);
    asserting one would fabricate provenance the data does not support.

This is model-level provenance, not the original measurement source (which is
generally unrecoverable from a CHEMKIN import). It is the floor, not the ceiling.

Idempotent and read-mostly: only NULL-source records are touched. ``--dry-run``
reports the counts without writing.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from database.models.kinetic_data import Kinetics
from database.models.kinetic_model import KineticsComment, ThermoComment
from database.models.thermo_transport import Thermo


class Command(BaseCommand):
    help = (
        "Backfill Thermo.source / Kinetics.source from the using kinetic model's "
        "source, only when unambiguous (one distinct source). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing.",
        )

    def _sources_by_record(self, Comment, fk):
        """record_id -> set of distinct non-null source ids of the using models."""
        by_record = defaultdict(set)
        for rec_id, source_id in (
            Comment.objects.filter(kinetic_model__source__isnull=False)
            .values_list(f"{fk}_id", "kinetic_model__source_id")
            .distinct()
        ):
            by_record[rec_id].add(source_id)
        return by_record

    def _backfill(self, Model, Comment, fk, dry_run):
        by_record = self._sources_by_record(Comment, fk)
        set_count = ambiguous = 0
        updates = []
        for rec_id, source_ids in by_record.items():
            if len(source_ids) > 1:
                ambiguous += 1
                continue
            updates.append((rec_id, next(iter(source_ids))))

        # Only touch records that currently have no source.
        null_ids = set(
            Model.objects.filter(
                id__in=[r for r, _ in updates], source__isnull=True
            ).values_list("id", flat=True)
        )
        to_apply = [(r, s) for r, s in updates if r in null_ids]

        if not dry_run and to_apply:
            with transaction.atomic():
                for rec_id, source_id in to_apply:
                    Model.objects.filter(id=rec_id).update(source_id=source_id)
        set_count = len(to_apply)
        already = len(updates) - len(to_apply)
        return set_count, ambiguous, already

    def handle(self, *args, **options):
        dry = options["dry_run"]

        t_set, t_amb, t_already = self._backfill(Thermo, ThermoComment, "thermo", dry)
        k_set, k_amb, k_already = self._backfill(
            Kinetics, KineticsComment, "kinetics", dry
        )

        verb = "Would set" if dry else "Set"
        self.stdout.write(
            self.style.SUCCESS(
                f"Thermo:   {verb} {t_set}; ambiguous (left NULL) {t_amb}; "
                f"already sourced {t_already}.\n"
                f"Kinetics: {verb} {k_set}; ambiguous (left NULL) {k_amb}; "
                f"already sourced {k_already}."
            )
        )
        if dry:
            self.stdout.write(self.style.WARNING("Dry run: no records written."))
