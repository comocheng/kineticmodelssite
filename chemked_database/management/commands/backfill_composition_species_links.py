"""Backfill ``CompositionSpecies.database_species`` from the stored InChI.

Every ChemKED composition species row already carries the species identity as a
string (``CompositionSpecies.inchi``), but the importer never resolves it to the
canonical ``database.Species`` foreign key -- so ``database_species`` is null on
all 22k rows. That left dataset->species provenance unjoinable via the FK even
though the matchable value (InChI) is present in the row.

This command closes that gap with the SAME matcher ``link_semantic_mappings``
uses for ``prom:`` species rows: exact InChI against ``Isomer.inchi``, then an
RDKit InChIKey fallback against the InChIKey ``ExternalIdentifier`` rows. Note
``CompositionSpecies.inchi`` is stored WITHOUT the ``InChI=`` prefix (e.g.
``1S/N2/c1-2``) while ``Isomer.inchi`` includes it, so we normalize first.

Idempotent: only rows whose resolved species differs from what is stored are
written. Read-only preview with ``--dry-run``.
"""

from django.core.management.base import BaseCommand

from chemked_database.models import CompositionSpecies
from database.models import Species
from provenance.models import ExternalIdentifier, IdentifierScheme

try:
    from rdkit import Chem
    from rdkit import RDLogger

    RDLogger.DisableLog("rdApp.*")
except ImportError:  # pragma: no cover
    Chem = None


def _norm_inchi(value):
    """Ensure the standard ``InChI=`` prefix (CompositionSpecies stores it bare)."""
    value = (value or "").strip()
    if not value:
        return ""
    return value if value.startswith("InChI=") else f"InChI={value}"


class Command(BaseCommand):
    help = (
        "Resolve CompositionSpecies.database_species from the stored inchi "
        "(exact Isomer.inchi, RDKit InChIKey fallback). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be linked without writing.",
        )

    def handle(self, *args, **options):
        inchi_map = {}
        for sp in Species.objects.prefetch_related("isomers").all():
            for iso in sp.isomers.all():
                if iso.inchi:
                    inchi_map.setdefault(iso.inchi, sp.pk)

        inchikey_map = dict(
            ExternalIdentifier.objects.filter(
                scheme=IdentifierScheme.INCHIKEY, content_type__model="species"
            ).values_list("value", "object_id")
        )

        valid_species = set(Species.objects.values_list("id", flat=True))

        linked = unresolved = unchanged = 0
        updates = []
        for cs in CompositionSpecies.objects.exclude(inchi="").only(
            "id", "inchi", "database_species_id"
        ):
            inchi = _norm_inchi(cs.inchi)
            species_id = inchi_map.get(inchi)
            if species_id is None and Chem is not None:
                key = Chem.InchiToInchiKey(inchi)
                if key:
                    species_id = inchikey_map.get(key)
            if species_id is None or species_id not in valid_species:
                unresolved += 1
                continue
            if cs.database_species_id == species_id:
                unchanged += 1
                continue
            cs.database_species_id = species_id
            updates.append(cs)
            linked += 1

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] would link {linked} CompositionSpecies "
                    f"({unchanged} already correct, {unresolved} unresolved)."
                )
            )
            return

        # Bulk update in chunks to avoid a giant single statement.
        CHUNK = 2000
        for i in range(0, len(updates), CHUNK):
            CompositionSpecies.objects.bulk_update(
                updates[i : i + CHUNK], ["database_species"]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Linked {linked} CompositionSpecies -> database.Species "
                f"({unchanged} already correct, {unresolved} unresolved)."
            )
        )
