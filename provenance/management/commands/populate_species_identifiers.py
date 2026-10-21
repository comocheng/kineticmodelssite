from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from database.models import Species
from provenance.models import ExternalIdentifier, IdentifierScheme

try:
    from rdkit import Chem
    from rdkit import RDLogger

    RDLogger.DisableLog("rdApp.*")
except ImportError:  # pragma: no cover
    Chem = None


class Command(BaseCommand):
    help = "Attach InChIKey/InChI/CAS ExternalIdentifiers to Species records (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0, help="Cap species processed (0 = all)."
        )

    def handle(self, *args, **options):
        if Chem is None:
            self.stderr.write(self.style.ERROR("RDKit not available; cannot derive InChIKey."))
            return

        ct = ContentType.objects.get_for_model(Species)
        qs = Species.objects.prefetch_related("isomers").all()
        if options["limit"]:
            qs = qs[: options["limit"]]

        created = 0
        for sp in qs:
            isomer = sp.isomers.first()
            inchi = isomer.inchi if isomer else ""

            if sp.cas_number:
                _, made = ExternalIdentifier.objects.update_or_create(
                    content_type=ct,
                    object_id=sp.pk,
                    scheme=IdentifierScheme.CAS,
                    value=sp.cas_number,
                    defaults={"is_primary": False},
                )
                created += int(made)

            if not inchi:
                continue

            key = Chem.InchiToInchiKey(inchi)
            if key:
                _, made = ExternalIdentifier.objects.update_or_create(
                    content_type=ct,
                    object_id=sp.pk,
                    scheme=IdentifierScheme.INCHIKEY,
                    value=key,
                    defaults={"is_primary": True},
                )
                created += int(made)

            _, made = ExternalIdentifier.objects.update_or_create(
                content_type=ct,
                object_id=sp.pk,
                scheme=IdentifierScheme.INCHI,
                value=inchi,
                defaults={"is_primary": False},
            )
            created += int(made)

        self.stdout.write(self.style.SUCCESS(f"Created {created} external identifiers."))
