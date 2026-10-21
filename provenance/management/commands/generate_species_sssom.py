"""Append kinetic-model *species* SSSOM rows to ``mappings/prometheus.sssom.tsv``.

``generate_sssom.py`` only resolves the handful of species that appear in
ChemKED experiment YAML.  The species that make up an imported kinetic model
(hundreds per mechanism, including radicals and intermediates) live in
``database.Species`` and were never cross-referenced, so the FAIR graph shows
only a sparse subset of each model's chemistry.

This command is the kinetic-model species counterpart.  For every distinct
species of the selected model(s) it:

  1. reads the structure already stored in the database (SMILES / Augmented
     InChI) -- no structures are invented;
  2. regenerates a **standard** InChIKey with RMG (the Augmented/RMG InChI in
     the database carries ``/u`` unpaired-electron and ``/lp`` lone-pair layers
     that external authorities do not accept, and naive stripping collapses a
     radical onto its closed-shell parent -- e.g. CH3 -> methane -- so RMG is
     used to obtain a faithful standard InChIKey that keeps the radical
     distinct); and
  3. resolves that **exact** InChIKey against PubChem (PUG REST) and EBI
     UniChem (ChEBI / ChEMBL / DrugBank / HMDB).

Emitted rows use ``prom:<species-name>`` subjects and store the database
**Augmented InChI** in ``subject_match_field`` so that ``link_semantic_mappings``
matches them to the exact ``database.Isomer`` and sets the ``species`` foreign
key -- which is what makes the model-uses-species provenance edges light up.

To avoid case-variant duplicate subjects (``prom:AR`` vs ``prom:Ar``), the
command reuses an existing subject when one already maps the *same InChIKey*
under a case-insensitive variant of the species name; requiring the InChIKey to
agree keeps distinct isomers spelled alike (``C3H3O`` vs ``c3h3o``) separate.

Rows are appended to the shared SSSOM TSV (no header rewrite) and the command is
idempotent: an existing ``(subject_id, predicate_id, object_id)`` is never
duplicated.  Follow with ``import_sssom`` -> ``link_semantic_mappings`` ->
``export_provenance_edges`` (then regenerate the TTL/HTML artifacts).

Network access is required unless ``--offline`` is given (offline emits only the
deterministic local InChIKey rows).  Be patient and kind to the public APIs: a
polite delay is inserted between calls.

Usage:
    manage.py generate_species_sssom --model 25
    manage.py generate_species_sssom --all
    manage.py generate_species_sssom --model 25 --offline --dry-run
"""

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models import KineticModel
from database.models.kinetic_model import SpeciesName
from database.models.reaction_species import Isomer, Structure

DEFAULT = Path(__file__).resolve().parents[4] / "mappings" / "sssom" / "prometheus.sssom.tsv"
AUTHOR_ID = "orcid:0000-0001-7137-5721"
PREDICATE = "skos:exactMatch"


def _curie_local(text: str) -> str:
    """Percent-encode only the characters that make a CURIE reference invalid
    (whitespace, brackets, non-ASCII), leaving chemistry punctuation such as
    ``( ) * . + -`` intact.  Reversible, so ``CHFCH[Z]`` -> ``CHFCH%5BZ%5D``.
    """
    return urllib.parse.quote(text or "", safe="!$&'()*+,;=@%")


USER_AGENT = "Prometheus-SSSOM-generator/1.0 (https://dev.omethe.us)"
HTTP_TIMEOUT = 20
POLITE_DELAY = 0.2

COLUMNS = [
    "subject_id",
    "subject_label",
    "predicate_id",
    "object_id",
    "object_label",
    "mapping_justification",
    "subject_match_field",
    "confidence",
    "mapping_tool",
    "mapping_date",
    "author_id",
    "comment",
]

# EBI UniChem source id -> (CURIE prefix, human label).  Subset of useful sources.
UNICHEM_SOURCES = {
    "1": ("chembl", "ChEMBL"),
    "2": ("drugbank", "DrugBank"),
    "7": ("CHEBI", "ChEBI"),
    "22": ("pubchem.compound", "PubChem"),
    "31": ("hmdb", "HMDB"),
}


def _get(url, *, data=None, headers=None):
    """HTTP request returning the body text, or None on failure."""
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - network is best-effort
        sys.stderr.write(f"  [warn] request failed ({exc}): {url}\n")
        return None
    finally:
        time.sleep(POLITE_DELAY)


def _pubchem_by_inchikey(inchikey):
    """Exact InChIKey -> {cid, name}.  Exact lookup avoids the radical-collapsing
    normalisation that PubChem's free-text InChI search performs."""
    if not inchikey:
        return {}
    cid_json = _get(
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/"
        f"{urllib.parse.quote(inchikey)}/cids/JSON"
    )
    if not cid_json:
        return {}
    try:
        cids = json.loads(cid_json)["IdentifierList"]["CID"]
    except (KeyError, ValueError, TypeError):
        return {}
    if not cids:
        return {}
    cid = cids[0]
    name = None
    prop_json = _get(
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}"
        "/property/IUPACName/JSON"
    )
    if prop_json:
        try:
            name = json.loads(prop_json)["PropertyTable"]["Properties"][0].get("IUPACName")
        except (KeyError, ValueError, TypeError, IndexError):
            pass
    return {"cid": cid, "name": name}


def _unichem_by_inchikey(inchikey):
    """InChIKey -> list of {src_id, compound_id} via EBI UniChem."""
    if not inchikey:
        return []
    payload = json.dumps({"type": "inchikey", "compound": inchikey}).encode()
    text = _get(
        "https://www.ebi.ac.uk/unichem/api/v1/compounds",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    results = []
    if not text:
        return results
    try:
        for compound in json.loads(text).get("compounds", []):
            for src in compound.get("sources", []):
                results.append(
                    {"src_id": str(src.get("id")), "compound_id": src.get("compoundId")}
                )
    except (ValueError, TypeError):
        pass
    return results


class Command(BaseCommand):
    help = (
        "Resolve a kinetic model's database species to PubChem/ChEBI/ChEMBL/"
        "DrugBank/HMDB and append prom: SSSOM rows (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=int,
            action="append",
            default=[],
            help="KineticModel primary key (repeatable). Omit with --all for every model.",
        )
        parser.add_argument(
            "--all", action="store_true", help="Process every kinetic model."
        )
        parser.add_argument("--path", default=str(DEFAULT))
        parser.add_argument(
            "--offline",
            action="store_true",
            help="Skip all network calls; emit only deterministic local InChIKey rows.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N species (0 = no limit). Useful for a smoke test.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the rows that would be appended without writing the file.",
        )

    # -- helpers ---------------------------------------------------------
    def _import_rmg(self):
        try:
            from rmgpy.molecule import Molecule
        except ImportError as exc:  # pragma: no cover
            self.stderr.write(
                self.style.ERROR(
                    f"RMG (rmgpy) is required for standard-InChIKey generation: {exc}"
                )
            )
            return None
        return Molecule

    @staticmethod
    def _representative_name(species_id):
        """Pick a stable, human-friendly species name (shortest, then alpha)."""
        names = [
            n
            for n in SpeciesName.objects.filter(species_id=species_id)
            .values_list("name", flat=True)
            .distinct()
            if n and n.strip()
        ]
        if not names:
            return None
        return sorted(names, key=lambda s: (len(s), s))[0].strip()

    @staticmethod
    def _structure_for(species_id):
        """Return (augmented_inchi, smiles) from the species' first isomer."""
        iso = Isomer.objects.filter(species=species_id).order_by("id").first()
        if not iso:
            return "", ""
        st = Structure.objects.filter(isomer=iso).order_by("id").first()
        return iso.inchi or "", (st.smiles if st else "") or ""

    def _standard_key(self, Molecule, smiles, augmented_inchi):
        """Standard (InChI, InChIKey) via RMG, preferring SMILES then InChI."""
        for loader, value in (("from_smiles", smiles), ("from_inchi", augmented_inchi)):
            if not value:
                continue
            try:
                mol = getattr(Molecule(), loader)(value)
                return mol.to_inchi(), mol.to_inchi_key()
            except Exception:  # noqa: BLE001 - try the next representation
                continue
        return "", ""

    # -- main ------------------------------------------------------------
    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"SSSOM file not found: {path}"))
            return

        if options["all"]:
            model_ids = list(KineticModel.objects.values_list("id", flat=True))
        else:
            model_ids = options["model"]
        if not model_ids:
            self.stderr.write(
                self.style.ERROR("Specify --model <pk> (repeatable) or --all.")
            )
            return

        offline = options["offline"]
        # RMG runs locally (no network); --offline only skips PubChem/UniChem.
        Molecule = self._import_rmg()
        if Molecule is None:
            return

        # Distinct species across the selected models.
        species_ids = list(
            SpeciesName.objects.filter(kinetic_model_id__in=model_ids)
            .values_list("species_id", flat=True)
            .distinct()
        )
        if options["limit"]:
            species_ids = species_ids[: options["limit"]]

        existing = set()
        # (lowercased species name, inchikey object) -> existing prom subject, so a
        # later mechanism spelling reuses the canonical IRI instead of minting a
        # case-variant duplicate (e.g. "AR" reuses prom:Ar). Requiring the InChIKey
        # to match keeps different isomers spelled alike (C3H3O vs c3h3o) apart.
        subject_by_key = {}
        with path.open(newline="", encoding="utf-8") as fh:
            data_lines = (line for line in fh if not line.startswith("#"))
            for row in csv.DictReader(data_lines, delimiter="\t"):
                s = row.get("subject_id")
                o = row.get("object_id")
                existing.add((s, row.get("predicate_id"), o))
                if s and s.startswith("prom:") and o and o.startswith("inchikey:"):
                    subject_by_key.setdefault(
                        (urllib.parse.unquote(s.split(":", 1)[1]).lower(), o), s
                    )

        today = date.today().isoformat()
        new_rows = []
        resolved = unresolved = skipped = 0

        self.stdout.write(
            f"Processing {len(species_ids)} distinct species "
            f"from {len(model_ids)} model(s)"
            + (" [offline]" if offline else "")
            + " ..."
        )

        for idx, sid in enumerate(species_ids, 1):
            name = self._representative_name(sid)
            augmented_inchi, smiles = self._structure_for(sid)
            if not name or not (augmented_inchi or smiles):
                skipped += 1
                continue

            _, inchikey = self._standard_key(Molecule, smiles, augmented_inchi)
            if not inchikey:
                unresolved += 1
                continue

            # Reuse the canonical subject if one already maps this exact InChIKey
            # under a case-variant of this name; otherwise mint prom:<name>.
            inchikey_obj = f"inchikey:{inchikey}"
            subject = subject_by_key.get((name.lower(), inchikey_obj))
            if subject is None:
                subject = f"prom:{_curie_local(name)}"
                subject_by_key[(name.lower(), inchikey_obj)] = subject
            subject_label = name

            def add(object_id, object_label, confidence, justification, tool, comment):
                key = (subject, PREDICATE, object_id)
                if key in existing:
                    return
                existing.add(key)
                new_rows.append(
                    [
                        subject,
                        subject_label,
                        PREDICATE,
                        object_id,
                        object_label,
                        justification,
                        augmented_inchi,
                        confidence,
                        tool,
                        today,
                        AUTHOR_ID,
                        comment,
                    ]
                )

            if inchikey:
                add(
                    f"inchikey:{inchikey}",
                    name,
                    "1.0",
                    "semapv:CompositionBasedMatch",
                    "generate_species_sssom (RMG)",
                    "Standard InChIKey regenerated from the database structure; "
                    "deterministic. Standard InChI does not encode spin state.",
                )

            if offline:
                resolved += 1
                continue

            pc = _pubchem_by_inchikey(inchikey)
            if pc.get("cid"):
                add(
                    f"pubchem.compound:{pc['cid']}",
                    pc.get("name") or name,
                    "0.95",
                    "semapv:CompositionBasedMatch",
                    "generate_species_sssom (PubChem)",
                    "Exact InChIKey match to PubChem; VERIFY before publish.",
                )
            for src in _unichem_by_inchikey(inchikey):
                mapping = UNICHEM_SOURCES.get(src["src_id"])
                if not mapping or not src.get("compound_id"):
                    continue
                prefix, label = mapping
                if prefix == "pubchem.compound":
                    continue  # already added
                compound_id = str(src["compound_id"])
                if compound_id.upper().startswith(f"{prefix.upper()}:"):
                    compound_id = compound_id.split(":", 1)[1]
                add(
                    f"{prefix}:{compound_id}",
                    label,
                    "0.9",
                    "semapv:CompositionBasedMatch",
                    "generate_species_sssom (UniChem)",
                    f"InChIKey cross-ref to {label} via UniChem; VERIFY.",
                )
            resolved += 1

            if not offline and idx % 25 == 0:
                self.stdout.write(f"  ... {idx}/{len(species_ids)} species processed")

        summary = (
            f"species resolved: {resolved}, unresolved: {unresolved}, "
            f"skipped (no name/structure): {skipped}; new rows: {len(new_rows)}"
        )

        if options["dry_run"]:
            for r in new_rows[:50]:
                self.stdout.write("\t".join(r))
            if len(new_rows) > 50:
                self.stdout.write(f"  ... ({len(new_rows) - 50} more)")
            self.stdout.write(self.style.SUCCESS(f"[dry-run] {summary}"))
            return

        if not new_rows:
            self.stdout.write(self.style.WARNING(f"No new rows. {summary}"))
            return

        with path.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write("\t".join(r) + "\n")
        self.stdout.write(
            self.style.SUCCESS(f"Appended {len(new_rows)} rows to {path.name}. {summary}")
        )
