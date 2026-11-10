"""Delete kinetics links whose reaction is not the equation their comment names.

rebuild_model_links keeps an old link when its model's library does not import whole. Some of
those old links were made before the clean-up corrected a species: in PCI2019/751-Chang,
ch2(s) <=> ch2 also links to CH2(T) = CH2(T). The model's names show it: written with them, the
reaction is not the equation in the link's comment. Run prune_unlinked_rows after it.

Usage:
    python manage.py prune_mismatched_links --report links.tsv          # dry run
    python manage.py prune_mismatched_links --apply --report links.tsv
"""
import csv
from collections import Counter

from django.core.management.base import BaseCommand

from database.services.cleanup import prune_mismatched_links


class Command(BaseCommand):
    help = "Delete kinetics links whose reaction is not the equation their comment names."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument("--report", help="Write one line per link to this TSV file.")

    def handle(self, *args, **options):
        rows = prune_mismatched_links(apply=options["apply"])
        if options["report"]:
            with open(options["report"], "w", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(["model", "link_id", "kinetics_id", "reaction_id", "comment"])
                for k in rows:
                    writer.writerow([k["kinetic_model__model_name"], k["id"], k["kinetics_id"],
                                     k["kinetics__reaction_id"], k["comment"]])
        for model, count in sorted(Counter(k["kinetic_model__model_name"] for k in rows).items()):
            self.stdout.write(f"{model}: {count}")
        self.stdout.write(f"kinetics links not their equation: {len(rows)}")
        self.stdout.write("applied" if options["apply"] else "dry run: nothing written")
