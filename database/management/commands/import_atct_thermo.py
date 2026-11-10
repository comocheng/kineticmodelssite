import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from database.services.thermo_sources import fetch_atct, import_atct


class Command(BaseCommand):
    help = "Import one ATcT gas-phase record by exact ID, retaining version and uncertainty."

    def add_arguments(self, parser):
        parser.add_argument("--atct-id", required=True)
        parser.add_argument("--multiplicity", type=int, required=True, help="Reviewed spin multiplicity")
        parser.add_argument("--state-label", required=True, help="Reviewed electronic state, e.g. ground state")
        parser.add_argument("--input-file", help="Previously retrieved ATcT API JSON object; skips the network request")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            if options["input_file"]:
                data = json.loads(Path(options["input_file"]).read_text())
                if not isinstance(data, dict) or data.get("ATcT_ID") != options["atct_id"]:
                    raise CommandError("Input JSON must contain the exact requested ATcT ID.")
            else:
                data = fetch_atct(options["atct_id"])
            with transaction.atomic():
                record = import_atct(data, multiplicity=options["multiplicity"], electronic_state=options["state_label"])
                if options["input_file"]:
                    record.provenance += " Imported from a previously retrieved API JSON snapshot; retrieved_at is the local import time."
                    record.save(update_fields=["provenance"])
                self.stdout.write(f"{record}; Hf(298.15 K) = {record.enthalpy_298:g} ± {record.uncertainty_298:g} J/mol")
                if options["dry_run"]:
                    transaction.set_rollback(True)
                    self.stdout.write("Dry run: nothing saved.")
        except Exception as exc:
            raise CommandError(str(exc)) from exc
