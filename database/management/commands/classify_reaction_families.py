from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from database import models
from database.services import rmg_matching
from database.services.rmg_families import FamilyClassifier, NO_FAMILY, UNSUPPORTED


class Command(BaseCommand):
    help = ("Classify each canonical reaction into an RMG reaction family and store RMG's rate-rule "
            "estimate. Slow (RMG family matching per reaction); resumes where it stopped.")

    def add_arguments(self, parser):
        parser.add_argument("--database-path", help="RMG-database checkout (default: RMG_DATABASE_PATH)")
        parser.add_argument("--limit", type=int, help="Classify at most this many canonical reactions")
        parser.add_argument("--reaction", type=int, action="append", help="Only this reaction id (repeatable)")
        parser.add_argument("--retry", action="store_true", help="Also retry reactions marked unsupported (?)")
        parser.add_argument("--estimates-only", action="store_true",
                            help="Recompute the rate-rule estimates of classified reactions, searching only their family")

    def handle(self, *args, **options):
        root = rmg_matching.database_root(options["database_path"])
        version = rmg_matching.database_version(root)
        self.stdout.write(f"Loading RMG families from {root} ({version})...")
        classifier = FamilyClassifier(root)
        if options["estimates_only"]:
            return self.re_estimate(classifier, version, options)
        pending = models.Reaction.objects.exclude(canonical_key="")
        if options["reaction"]:
            pending = pending.filter(pk__in=options["reaction"])
        else:
            pending = pending.filter(rmg_family__in=["", UNSUPPORTED] if options["retry"] else [""])
        counts, seen = Counter(), set()
        for reaction in pending.order_by("pk").iterator():
            if reaction.canonical_key in seen:
                continue
            seen.add(reaction.canonical_key)
            try:
                with transaction.atomic():
                    result = classifier.classify(reaction, version)
            except Exception as exc:
                models.Reaction.objects.filter(canonical_key=reaction.canonical_key).update(rmg_family=UNSUPPORTED)
                self.stderr.write(f"reaction {reaction.pk}: {type(exc).__name__}: {exc}")
                result = UNSUPPORTED
            counts["no family" if result == NO_FAMILY else "unsupported" if result == UNSUPPORTED else "classified"] += 1
            done = sum(counts.values())
            if done % 100 == 0:
                self.stdout.write(f"{done} canonical reactions: {dict(counts)}")
                self.stdout.flush()
            if options["limit"] and done >= options["limit"]:
                break
        self.stdout.write(f"Done: {dict(counts)}")

    def re_estimate(self, classifier, version, options):
        pending = models.Reaction.objects.exclude(canonical_key="").exclude(rmg_family__in=["", NO_FAMILY, UNSUPPORTED])
        if options["reaction"]:
            pending = pending.filter(pk__in=options["reaction"])
        counts, seen = Counter(), set()
        for reaction in pending.order_by("pk").iterator():
            if reaction.canonical_key in seen:
                continue
            seen.add(reaction.canonical_key)
            try:
                with transaction.atomic():
                    counts["estimated" if classifier.re_estimate(reaction, version) else "no estimate"] += 1
            except Exception as exc:
                counts["no estimate"] += 1
                self.stderr.write(f"reaction {reaction.pk}: {type(exc).__name__}: {exc}")
            done = sum(counts.values())
            if done % 500 == 0:
                self.stdout.write(f"{done} canonical reactions: {dict(counts)}")
                self.stdout.flush()
            if options["limit"] and done >= options["limit"]:
                break
        self.stdout.write(f"Done: {dict(counts)}")
