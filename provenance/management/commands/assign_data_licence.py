"""Give every experimental dataset the licence of the data that the site curates
(settings.DATA_LICENSE_SPDX). Kinetic models keep the terms of their source publication and are not
changed. A dry run by default; --apply writes."""
from django.core.management.base import BaseCommand

from chemked_database.models import ExperimentDataset
from provenance.data_licence import apply_data_licence


class Command(BaseCommand):
    help = "Set the licence of every dataset to settings.DATA_LICENSE_SPDX (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the licences.")

    def handle(self, *args, **options):
        apply_data_licence([ExperimentDataset.objects.all()], self.stdout.write, apply=options["apply"])
