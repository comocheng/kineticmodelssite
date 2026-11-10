"""Give every record its canonical key (the /id/<kind>/<key> URL), and keep the keys of records
that changed or were removed as redirects and tombstones. A dry run by default; --apply writes.

Run it after an import, after a clean-up that merges or removes records, and after a rebuild of
the database: the keys come from the chemistry and the outside identifiers, so a rebuild gives
the same keys."""
from django.core.management.base import BaseCommand, CommandError

from provenance.record_key_sync import assign
from provenance.record_keys import KINDS


class Command(BaseCommand):
    help = "Assign the canonical keys of the records (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the keys.")
        parser.add_argument("--kind", action="append", choices=sorted(KINDS),
                            help="Only this kind of record (may be given more than once).")
        parser.add_argument("--examples", action="store_true", help="Print up to 5 shared keys of each kind.")

    def handle(self, *args, **options):
        kinds = options["kind"] or list(KINDS)
        unknown = set(kinds) - set(KINDS)
        if unknown:
            raise CommandError(f"unknown kinds: {sorted(unknown)}")
        self.stdout.write("Writing the keys." if options["apply"] else "Dry run: nothing is written (use --apply).")
        for kind in kinds:
            result = assign(kind, apply=options["apply"])
            self.stdout.write(result.line())
            if options["examples"]:
                for key in result.examples:
                    self.stdout.write(f"    shared: {key}")
