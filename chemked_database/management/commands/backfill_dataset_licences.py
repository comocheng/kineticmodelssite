"""Give every dataset without a licence the licence of the ChemKED-database repository.

The licence is the ``license:`` of the repository's CITATION.cff (an SPDX id, CC-BY-4.0 for
pr-omethe-us/ChemKED-database). A dry run by default; --apply writes.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chemked_database.licences import assign_repository_licence
from chemked_database.models import ExperimentDataset


class Command(BaseCommand):
    help = "Set ExperimentDataset.license from the repository's CITATION.cff (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=getattr(settings, "CHEMKED_DATABASE_PATH", None),
                            help="ChemKED-database checkout (default CHEMKED_DATABASE_PATH).")
        parser.add_argument("--apply", action="store_true", help="Write the licences.")

    def handle(self, *args, **options):
        if not options["path"]:
            raise CommandError("Provide --path or set CHEMKED_DATABASE_PATH in settings.")
        assign_repository_licence(options["path"], ExperimentDataset.objects.all(), self.stdout.write,
                                  apply=options["apply"])
