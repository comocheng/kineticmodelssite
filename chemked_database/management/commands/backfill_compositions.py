from django.core.management.base import BaseCommand
from django.db import transaction

from chemked_database.models import Composition, CompositionSpecies, ExperimentDatapoint


class Command(BaseCommand):
    help = "Backfill and clean null composition links for ChemKED datasets"

    def handle(self, *args, **options):
        created = 0
        linked = 0
        updated_datapoints = 0

        with transaction.atomic():
            for datapoint in ExperimentDatapoint.objects.filter(composition__isnull=True):
                common = getattr(datapoint.dataset, "common_properties", None)
                if common and common.composition:
                    datapoint.composition = common.composition
                    datapoint.save(update_fields=["composition"])
                    updated_datapoints += 1
                    continue

                composition = Composition.objects.create(kind="")
                datapoint.composition = composition
                datapoint.save(update_fields=["composition"])
                created += 1

            for species in CompositionSpecies.objects.filter(composition__isnull=True):
                datapoint = getattr(species, "datapoint", None)
                if datapoint and datapoint.composition:
                    species.composition = datapoint.composition
                    species.save(update_fields=["composition"])
                    linked += 1
                else:
                    composition = Composition.objects.create(kind="")
                    species.composition = composition
                    species.save(update_fields=["composition"])
                    created += 1

        self.stdout.write(
            f"Backfill complete. New compositions: {created}, linked species: {linked},"
            f" updated datapoints: {updated_datapoints}"
        )
