from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from database.services import rmg_matching


class Command(BaseCommand):
    help = ("Match the site's reactions and species to RMG-database kinetics and thermo libraries, "
            "store the counterparts as source records, and summarize each model's overlap with each library.")

    def add_arguments(self, parser):
        parser.add_argument("--database-path", help="RMG-database checkout (default: RMG_DATABASE_PATH)")
        parser.add_argument("--library", action="append", help="Only this library (repeatable), e.g. GRI-Mech3.0")
        parser.add_argument("--skip-kinetics", action="store_true")
        parser.add_argument("--skip-thermo", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = rmg_matching.database_root(options["database_path"])
        version = rmg_matching.database_version(root)
        wanted = set(options["library"] or [])
        self.stdout.write(f"RMG-database {root} ({version})")
        totals, failures = Counter(), []
        with transaction.atomic():
            if not options["skip_kinetics"]:
                index = rmg_matching.site_reaction_index()
                for label, path in rmg_matching.kinetics_libraries(root):
                    if wanted and label not in wanted:
                        continue
                    try:
                        with transaction.atomic():
                            stats = rmg_matching.match_kinetics_library(label, path, version, index)
                    except Exception as exc:
                        failures.append(f"kinetics {label}: {exc}")
                        continue
                    totals.update({f"kinetics {k}": v for k, v in stats.items()})
                    self.stdout.write(f"  kinetics {label}: {stats['matched']} of {stats['entries']} entries matched")
                self.stdout.write(f"Kinetics overlap rows: {rmg_matching.kinetics_overlaps(version)}")
            if not options["skip_thermo"]:
                structures = rmg_matching.structures_by_key()
                for label, path in rmg_matching.thermo_libraries(root):
                    if wanted and label not in wanted:
                        continue
                    try:
                        with transaction.atomic():
                            stats = rmg_matching.match_thermo_library(label, path, version, structures)
                    except Exception as exc:
                        failures.append(f"thermo {label}: {exc}")
                        continue
                    totals.update({f"thermo {k}": v for k, v in stats.items()})
                    self.stdout.write(f"  thermo {label}: {stats['matched']} of {stats['entries']} entries matched")
                self.stdout.write(f"Thermo overlap rows: {rmg_matching.thermo_overlaps(version)}")
            if options["dry_run"]:
                transaction.set_rollback(True)
        for failure in failures:
            self.stderr.write(f"Not loaded: {failure}")
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in sorted(totals.items())))
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing saved.")
