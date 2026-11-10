"""Backfill ``CompositionSpecies.database_species`` from the stored InChI.

Every ChemKED composition species row carries the species identity as a string
(``CompositionSpecies.inchi``). ``sync_chemked`` links new rows at ingest; this command links
the rows stored before that, and corrects links made by the earlier rule.

The rule is the one ``sync_chemked`` uses (``chemked_database.species_links``): the component's
standard InChI against the records' InChIs without RMG's /u and /lp layers, then an RDKit
InChIKey fallback against ``Structure.structure_key``. When records of several spins share the
standard InChI, the component is the ground state (triplet O2, not singlet O2). The earlier rule
matched the exact ``Isomer.inchi`` first, and the standard InChI of O2 is exactly the singlet
record's InChI, so O2 was linked to singlet O2.

A row's link is made to agree with its InChI: a row whose InChI matches no record, or records of
several spins without a ground state in the table, loses a link it had. Rows without an InChI
are left as they are. Idempotent: only rows whose link changes are written. Read-only preview
with ``--dry-run``.
"""

from collections import Counter

from django.core.management.base import BaseCommand

from chemked_database.models import CompositionSpecies
from chemked_database.species_links import SpeciesLinker


class Command(BaseCommand):
    help = (
        "Resolve CompositionSpecies.database_species from the stored inchi "
        "(standard InChI, ground state of records with several spins). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be linked without writing.",
        )

    def handle(self, *args, **options):
        linker = SpeciesLinker()
        counts = Counter()
        unresolved = Counter()
        updates = []
        for cs in CompositionSpecies.objects.exclude(inchi="").only(
            "id", "inchi", "database_species_id"
        ):
            species_id, how = linker.resolve(cs.inchi)
            if species_id is None:
                unresolved[how] += 1
            if cs.database_species_id == species_id:
                counts["unchanged"] += 1
                continue
            if species_id is None:
                counts["unlinked"] += 1
            elif cs.database_species_id is None:
                counts["linked"] += 1
            else:
                counts["relinked"] += 1
            cs.database_species_id = species_id
            updates.append(cs)

        summary = (
            f"{counts['linked']} linked, {counts['relinked']} moved to another record, "
            f"{counts['unlinked']} unlinked, {counts['unchanged']} unchanged; without a record: "
            + (", ".join(f"{n} ({why})" for why, n in sorted(unresolved.items())) or "none")
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"[dry-run] would write: {summary}."))
            return

        # Bulk update in chunks to avoid a giant single statement.
        CHUNK = 2000
        for i in range(0, len(updates), CHUNK):
            CompositionSpecies.objects.bulk_update(
                updates[i : i + CHUNK], ["database_species"]
            )

        self.stdout.write(self.style.SUCCESS(f"CompositionSpecies -> database.Species: {summary}."))
