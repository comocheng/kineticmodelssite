from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from database.models import Species
from database.services.chemical_identity import inchikey_of
from provenance.models import ExternalIdentifier, IdentifierScheme

# Schemes whose ExternalIdentifier rows are copies of database fields. Structure
# (structure_key, pubchem_cid, canonical_smiles) is the source of truth for the
# first three; Isomer.inchi and Species.cas_number for the last two.
MIRRORED_SCHEMES = (
    IdentifierScheme.INCHIKEY,
    IdentifierScheme.PUBCHEM,
    IdentifierScheme.SMILES,
    IdentifierScheme.INCHI,
    IdentifierScheme.CAS,
)


class Command(BaseCommand):
    help = (
        "Copy each species' InChIKey, PubChem CID and SMILES from its structures, and its "
        "InChI and CAS number, into ExternalIdentifier rows (idempotent). Rows of these "
        "schemes that no longer match the database fields are removed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0, help="Cap species processed (0 = all)."
        )

    def handle(self, *args, **options):
        ct = ContentType.objects.get_for_model(Species)
        qs = Species.objects.prefetch_related("isomers").order_by("pk")
        if options["limit"]:
            qs = qs[: options["limit"]]

        created = removed = 0
        for sp in qs:
            structures = list(
                sp.structures.values_list("structure_key", "pubchem_cid", "canonical_smiles")
            )
            inchikeys = sorted({inchikey_of(key) for key, _, _ in structures} - {""})

            wanted = {}
            for key in inchikeys:
                wanted[(IdentifierScheme.INCHIKEY.value, key)] = len(inchikeys) == 1
            for cid in sorted({cid for _, cid, _ in structures if cid}):
                wanted[(IdentifierScheme.PUBCHEM.value, str(cid))] = False
            for smiles in sorted({smiles for _, _, smiles in structures if smiles}):
                wanted[(IdentifierScheme.SMILES.value, smiles)] = False
            for isomer in sp.isomers.all():
                if isomer.inchi:
                    wanted[(IdentifierScheme.INCHI.value, isomer.inchi)] = False
            if sp.cas_number:
                wanted[(IdentifierScheme.CAS.value, sp.cas_number)] = False

            for (scheme, value), is_primary in wanted.items():
                _, made = ExternalIdentifier.objects.update_or_create(
                    content_type=ct,
                    object_id=sp.pk,
                    scheme=scheme,
                    value=value,
                    defaults={"is_primary": is_primary},
                )
                created += int(made)

            stale = [
                row.pk
                for row in ExternalIdentifier.objects.filter(
                    content_type=ct, object_id=sp.pk, scheme__in=MIRRORED_SCHEMES
                )
                if (row.scheme, row.value) not in wanted
            ]
            if stale:
                removed += ExternalIdentifier.objects.filter(pk__in=stale).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} external identifiers; removed {removed} that no longer "
                "match the database."
            )
        )
