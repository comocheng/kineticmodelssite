"""Append chemical-reaction identity rows to ``mappings/prometheus.sssom.tsv``.

A rate coefficient describes a *reaction* (A + B -> C), not any single species, so
reaction-level provenance ("this reaction's rate came from publication X") needs a
node for the reaction itself. This command mints one ``promrxn:<hash>`` node per
:class:`Reaction` that has at least one :class:`Kinetics` carrying a ``source``
(populate it first with ``backfill_thermo_kinetics_sources``) -- minting only the
reactions that can actually anchor a ``kineticsFrom`` edge keeps the node set
meaningful rather than minting the entire mechanism space.

Each node is anchored to its ontology *type* with ``skos:broadMatch`` to
``ontokin:GasPhaseReaction`` -- the generic class is broader than the specific
reaction instance, so this is a type assertion, not an external-identity claim
(reaction instances have no external registry). The minted node becomes a graph
subject; ``link_semantic_mappings`` then attaches the ``Reaction`` foreign key
(matching on ``Reaction.hash``), and ``export_provenance_edges`` resolves the
``kinetics data from`` edges automatically.

Append-only and idempotent: skips any ``(subject, predicate, object)`` already
present. Run after the backfill, then ``import_sssom`` and ``link_semantic_mappings``.
"""

import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models import Reaction
from database.models.reaction_species import Stoichiometry
from database.models.kinetic_model import SpeciesName

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:broadMatch"
OBJECT = "ontokin:GasPhaseReaction"
JUSTIFICATION = "semapv:UnspecifiedMatching"
TOOL = "generate_reaction_sssom"


class Command(BaseCommand):
    help = (
        "Append promrxn: SSSOM rows for reactions that have a sourced rate "
        "expression to prometheus.sssom.tsv (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT))
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the rows that would be appended without writing the file.",
        )

    def _species_names(self):
        """species_id -> a short display name (first model name, else formula)."""
        names = {}
        for sid, name in SpeciesName.objects.exclude(name="").values_list(
            "species_id", "name"
        ):
            names.setdefault(sid, name)
        return names

    def _reaction_label(self, coeffs, names):
        """Build 'A + B <=> C' from [(coeff, species_id)] tuples."""
        reactants, products = [], []
        for coeff, sid in coeffs:
            token = names.get(sid, f"sp{sid}")
            (reactants if coeff < 0 else products).append(token)
        lhs = " + ".join(sorted(reactants)) or "?"
        rhs = " + ".join(sorted(products)) or "?"
        return f"{lhs} <=> {rhs}"

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"SSSOM file not found: {path}"))
            return

        existing_keys = set()
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                existing_keys.add(
                    (
                        row.get("subject_id") or "",
                        row.get("predicate_id"),
                        row.get("object_id") or "",
                    )
                )

        today = date.today().isoformat()

        reaction_ids = list(
            Reaction.objects.filter(kinetics__source__isnull=False)
            .values_list("id", flat=True)
            .distinct()
        )
        hashes = dict(
            Reaction.objects.filter(id__in=reaction_ids).values_list("id", "hash")
        )

        # One pass over Stoichiometry to build each reaction's species/coeffs.
        coeffs_by_reaction = {}
        for rid, sid, coeff in Stoichiometry.objects.filter(
            reaction_id__in=reaction_ids
        ).values_list("reaction_id", "species_id", "coeff"):
            coeffs_by_reaction.setdefault(rid, []).append((coeff, sid))
        names = self._species_names()

        new_rows = []
        for rid in reaction_ids:
            rhash = hashes.get(rid)
            if not rhash:
                continue
            subject = f"promrxn:{rhash}"
            key = (subject, PREDICATE, OBJECT)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            label = self._reaction_label(coeffs_by_reaction.get(rid, []), names)
            new_rows.append(
                [
                    subject, label, PREDICATE, OBJECT, "Gas-Phase Reaction",
                    JUSTIFICATION, "reaction.hash", "1.0", TOOL, today, AUTHOR_ID,
                    "Reaction instance typed against the ontokin:GasPhaseReaction class.",
                ]
            )

        if not new_rows:
            self.stdout.write(
                self.style.WARNING("No new reaction rows -- all already covered.")
            )
            return

        if options["dry_run"]:
            for r in new_rows[:20]:
                self.stdout.write("\t".join(r))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[dry-run] {len(new_rows)} promrxn rows would be appended."
                )
            )
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Appended {len(new_rows)} promrxn rows to {path.name}."
            )
        )
