from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from database.models import ThermoRecord
from database.services.thermo_sources import ThermoSourceError, derive_atct_constrained


class Command(BaseCommand):
    help = "Build ATcT-constrained RMG thermo: Burcat or group-additivity NASA polynomials moved to the ATcT 298.15 K enthalpy."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        counts, problems = Counter(), []
        with transaction.atomic():
            for record in ThermoRecord.objects.filter(provider="atct").select_related("structure__isomer").order_by("pk"):
                try:
                    derived = derive_atct_constrained(record)
                except ThermoSourceError as exc:
                    problems.append(f"{record.external_id}: {exc}")
                    continue
                counts["derived records"] += len(derived)
                counts["ATcT records with a Cp/S source" if derived else "ATcT records without a Cp/S source"] += 1
            if options["dry_run"]:
                transaction.set_rollback(True)
        for key, value in sorted(counts.items()):
            self.stdout.write(f"{key}: {value}")
        for problem in problems:
            self.stderr.write(problem)
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing saved.")
        if problems:
            kept = "nothing saved" if options["dry_run"] else "the rest were saved"
            raise CommandError(f"{len(problems)} ATcT record(s) could not be constrained; {kept}.")
