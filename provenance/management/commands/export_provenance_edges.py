"""Export the provenance edges that connect the SSSOM nodes to each other.

The SSSOM mapping set (``prometheus.sssom.tsv``) is an *identifier crosswalk*:
every row maps one local entity to one external authority id, so the graph it
draws is intentionally a field of disconnected stars.  The relationships that
actually tie those entities together -- which species a kinetic model uses,
which publication a dataset cites -- live in the platform database as foreign
keys, not as mappings, so they are deliberately *not* in the SSSOM file.

This command reads those database relationships and emits them as a sidecar so
the interactive graph (``sssom_graph.py``) can overlay a connectivity layer on
top of the pure mapping set, without polluting the SSSOM artifact.  Endpoints are
the existing SSSOM subject CURIEs (resolved via the populated SemanticMapping
foreign keys), so an edge is only emitted when *both* of its nodes already exist
in the graph.

Two outputs (both beside the TSV by default):
  * ``prometheus.provenance.json`` -- typed edges for the HTML graph overlay.
  * ``prometheus.provenance.ttl``  -- the same edges as RDF, designed to be
    loaded *alongside* ``prometheus.sssom.ttl``: shared IRIs connect the two
    layers into one knowledge graph (SSSOM = authority bridges, this = domain
    links) without merging provenance into the mapping set.

Relationship types (all kept even when a type currently resolves to zero edges,
so the overlay lights up automatically as coverage improves):
  * ``uses``     KineticModel       --> Species          (via SpeciesName)
  * ``cites``    ExperimentDataset  --> publication       (promds <-> promref)
  * ``contains`` ExperimentDataset  --> Species          (via CompositionSpecies)
  * ``from``     KineticModel       --> Source/publication (model's reference)
  * ``locatedAt``     Apparatus     --> Institution       (apparatus's operating org)
  * ``usesApparatus`` ExperimentDataset --> Apparatus     (dataset's apparatus)
  * ``usesReaction``  KineticModel  --> Reaction         (via KineticsComment)
  * ``thermoFrom``    Species       --> KineticModel      (via ThermoComment)
  * ``kineticsFrom``  Reaction      --> KineticModel      (via KineticsComment)

A separate sidecar (``prometheus.reactions.json``) carries the reaction
stoichiometry as ``hasReactant``/``hasProduct`` edges (Reaction --> Species), so
the graph can reconstruct a reaction from its species and toggle that layer on
its own.

Read-only against the database; idempotent (overwrites the sidecars).
"""

import json
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from chemked_database.models import Apparatus, CompositionSpecies, ExperimentDataset
from database.models import KineticModel
from database.models.kinetic_model import SpeciesName
from database.models.kinetic_model import KineticsComment
from database.models.kinetic_model import ThermoComment
from database.models.reaction_species import Stoichiometry
from provenance.models import SemanticMapping
# Sidecars live beside the SSSOM artifacts in the sibling mappings/ directory.
# This file: <Prometheus>/kineticmodelssite/provenance/management/commands/<this>
#            parents: [0]commands [1]management [2]provenance [3]kineticmodelssite
#                     [4]Prometheus
MAPPINGS_DIR = Path(__file__).resolve().parents[4] / "mappings"
DEFAULT_JSON = MAPPINGS_DIR / "sssom" / "prometheus.provenance.json"
DEFAULT_TTL = MAPPINGS_DIR / "rdf" / "prometheus.provenance.ttl"
DEFAULT_RXN = MAPPINGS_DIR / "sssom" / "prometheus.reactions.json"

# Local domain predicates for the RDF (knowledge-graph) serialization.
PROMV = "https://dev.omethe.us/vocab/"
PROV = "http://www.w3.org/ns/prov#"
# OntoKin / OntoCAPE reaction-mechanism predicates for the reaction <-> species
# structural links (reaction has these reactants / products).
ONTOKIN_RXNMECH = (
    "http://www.theworldavatar.com/ontology/ontocape/material/substance/"
    "reaction_mechanism.owl#"
)
PREDICATE_IRI = {
    "uses": PROMV + "usesSpecies",
    "contains": PROMV + "containsSpecies",
    "cites": "http://purl.org/dc/terms/references",
    "from": "http://purl.org/dc/terms/source",
    "locatedAt": PROMV + "locatedAtInstitution",
    "usesApparatus": PROMV + "usesApparatus",
    "usesReaction": PROMV + "usesReaction",
    "thermoFrom": PROV + "wasDerivedFrom",
    "kineticsFrom": PROV + "wasDerivedFrom",
    "hasReactant": ONTOKIN_RXNMECH + "hasReactant",
    "hasProduct": ONTOKIN_RXNMECH + "hasProduct",
}


def _predicate_curie(kind):
    """Ontology-compatible CURIE for an edge kind (e.g. ``prov:wasDerivedFrom``)."""
    pred = PREDICATE_IRI[kind]
    if pred.startswith("http://purl.org/dc/terms/"):
        return "dcterms:" + pred.rsplit("/", 1)[1]
    if pred.startswith(PROV):
        return "prov:" + pred.rsplit("#", 1)[1]
    return "promv:" + pred.rsplit("/", 1)[1]


def _norm_doi(value):
    return (value or "").strip().lower().rstrip("/")


def _norm_inchi(value):
    """Normalize an InChI string so the ``InChI=`` prefix is always present."""
    value = (value or "").strip()
    if not value:
        return ""
    return value if value.startswith("InChI=") else "InChI=" + value


# Sub-delimiter characters that a Turtle PN_LOCAL may contain only when
# backslash-escaped (the PN_LOCAL_ESC production).
_PN_LOCAL_ESC = set("~!$&'()*+,;=/?#@-._")
_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")


def _escape_pn_local(local):
    """Escape a CURIE local part into a valid Turtle PN_LOCAL.

    Combustion species names carry characters (``* ( ) = , # @`` and percent
    escapes) that are legal in a CURIE only when escaped, so rather than fall
    back to a verbose full ``<IRI>`` we emit the proper escaped CURIE.  Letters,
    digits and ``_`` pass through; ``-``/``.`` are kept except where the grammar
    forbids them unescaped (leading ``-``/``.``, trailing ``.``); existing
    ``%HH`` percent-encoding is preserved; the remaining sub-delimiters are
    backslash-escaped.  Returns ``None`` if a character cannot be represented
    (caller then falls back to a full ``<IRI>``).
    """
    if not local or local[-1] == ".":
        # rdflib's Turtle parser rejects a trailing escaped ``\.``; fall back to
        # a full <IRI> for a local part that ends in a dot.
        return None
    out = []
    i, n = 0, len(local)
    while i < n:
        c = local[i]
        if c == "%" and _PERCENT.match(local, i):
            out.append(local[i:i + 3])
            i += 3
            continue
        if c.isalnum() or c == "_" or ord(c) > 127:
            out.append(c)
        elif c == "-":
            out.append("\\-" if i == 0 else "-")
        elif c == ".":
            out.append("\\." if i == 0 else ".")
        elif c in _PN_LOCAL_ESC:
            out.append("\\" + c)
        else:
            return None
        i += 1
    return "".join(out)


class Command(BaseCommand):
    help = (
        "Export database provenance edges (KM-uses-species, dataset-cites-"
        "publication, ...) as a sidecar for the SSSOM graph overlay."
    )

    def add_arguments(self, parser):
        parser.add_argument("--json", default=str(DEFAULT_JSON))
        parser.add_argument("--ttl", default=str(DEFAULT_TTL))
        parser.add_argument("--reactions", default=str(DEFAULT_RXN))
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report edge counts without writing the sidecars.",
        )

    # -- node resolution -------------------------------------------------
    def _resolve_nodes(self):
        """Map each DB entity id -> the SSSOM subject CURIEs that represent it."""
        ds_subjects = defaultdict(set)
        km_subject = {}
        sp_subjects = defaultdict(set)
        sp_by_inchi = defaultdict(set)
        promref_by_doi = {}
        app_subject = {}
        inst_subject = {}
        rxn_subject = {}

        for r in SemanticMapping.objects.filter(
            experiment_dataset__isnull=False
        ).values("experiment_dataset_id", "subject_id"):
            ds_subjects[r["experiment_dataset_id"]].add(r["subject_id"])
        for r in SemanticMapping.objects.filter(
            kinetic_model__isnull=False
        ).values("kinetic_model_id", "subject_id"):
            km_subject[r["kinetic_model_id"]] = r["subject_id"]
        for r in SemanticMapping.objects.filter(
            apparatus__isnull=False
        ).values("apparatus_id", "subject_id"):
            app_subject.setdefault(r["apparatus_id"], r["subject_id"])
        for r in SemanticMapping.objects.filter(
            institution__isnull=False
        ).values("institution_id", "subject_id"):
            inst_subject.setdefault(r["institution_id"], r["subject_id"])
        for r in SemanticMapping.objects.filter(
            reaction__isnull=False
        ).values("reaction_id", "subject_id"):
            rxn_subject.setdefault(r["reaction_id"], r["subject_id"])
        for r in SemanticMapping.objects.filter(species__isnull=False).values(
            "species_id", "subject_id", "subject_match_field"
        ):
            sp_subjects[r["species_id"]].add(r["subject_id"])
            inchi = _norm_inchi(r["subject_match_field"])
            if inchi:
                sp_by_inchi[inchi].add(r["subject_id"])
        for r in SemanticMapping.objects.filter(
            subject_id__startswith="promref:", object_id__startswith="doi:"
        ).values("subject_id", "object_id"):
            promref_by_doi.setdefault(
                _norm_doi(r["object_id"][len("doi:"):]), r["subject_id"]
            )
        return (
            ds_subjects,
            km_subject,
            sp_subjects,
            sp_by_inchi,
            promref_by_doi,
            app_subject,
            inst_subject,
            rxn_subject,
        )

    @staticmethod
    def _dataset_anchor(subjects):
        """Prefer the dataset-identity (promds) node as a dataset's anchor."""
        promds = sorted(s for s in subjects if s.startswith("promds:"))
        if promds:
            return promds[0]
        promref = sorted(s for s in subjects if s.startswith("promref:"))
        return promref[0] if promref else None

    # -- main ------------------------------------------------------------
    def handle(self, *args, **options):
        (
            ds_subjects,
            km_subject,
            sp_subjects,
            sp_by_inchi,
            promref_by_doi,
            app_subject,
            inst_subject,
            rxn_subject,
        ) = self._resolve_nodes()

        edges = []
        seen = set()

        def emit(src, dst, kind):
            if not src or not dst or src == dst:
                return
            key = (src, dst, kind)
            if key in seen:
                return
            seen.add(key)
            edges.append(
                {
                    "from": src,
                    "to": dst,
                    "kind": kind,
                    "predicate": _predicate_curie(kind),
                }
            )

        # (1) KineticModel --uses--> Species
        for sn in (
            SpeciesName.objects.filter(
                kinetic_model_id__in=km_subject.keys(),
                species_id__in=sp_subjects.keys(),
            )
            .values("kinetic_model_id", "species_id")
            .distinct()
        ):
            src = km_subject.get(sn["kinetic_model_id"])
            for dst in sp_subjects.get(sn["species_id"], ()):
                emit(src, dst, "uses")

        # (2) ExperimentDataset --cites--> publication (promds <-> promref)
        for ds_id, subjects in ds_subjects.items():
            anchor = self._dataset_anchor(subjects)
            for s in subjects:
                if s.startswith("promref:"):
                    emit(anchor, s, "cites")

        # (3) ExperimentDataset --contains--> Species (via CompositionSpecies).
        # CompositionSpecies.database_species is not backfilled, but each row
        # carries the raw InChI, so match that to the InChI-keyed species nodes
        # (same basis the SSSOM species rows use) and walk composition ->
        # datapoints -> dataset for the anchor.
        comp_pairs = (
            CompositionSpecies.objects.exclude(inchi="")
            .values("inchi", "composition__datapoints__dataset_id")
            .distinct()
        )
        for cp in comp_pairs:
            ds_id = cp["composition__datapoints__dataset_id"]
            if ds_id is None:
                continue
            dsts = sp_by_inchi.get(_norm_inchi(cp["inchi"]))
            if not dsts:
                continue
            anchor = self._dataset_anchor(ds_subjects.get(ds_id, set()))
            for dst in dsts:
                emit(anchor, dst, "contains")

        # (4) KineticModel --from--> publication (model's Source DOI)
        for km in KineticModel.objects.filter(
            id__in=km_subject.keys(), source__isnull=False
        ).select_related("source"):
            doi = _norm_doi(getattr(km.source, "doi", ""))
            dst = promref_by_doi.get(doi) if doi else None
            emit(km_subject.get(km.id), dst, "from")

        # (5) Apparatus --locatedAt--> Institution (apparatus -> operating org)
        for ap in Apparatus.objects.filter(
            id__in=app_subject.keys(), institution_ref__isnull=False
        ).values("id", "institution_ref_id"):
            emit(
                app_subject.get(ap["id"]),
                inst_subject.get(ap["institution_ref_id"]),
                "locatedAt",
            )

        # (6) ExperimentDataset --usesApparatus--> Apparatus
        for ds in ExperimentDataset.objects.filter(
            apparatus__isnull=False
        ).values("id", "apparatus_id"):
            anchor = self._dataset_anchor(ds_subjects.get(ds["id"], set()))
            emit(anchor, app_subject.get(ds["apparatus_id"]), "usesApparatus")

        # (7) Species --thermoFrom--> KineticModel (via ThermoComment).
        # The thermo values were parsed from a mechanism file, so the data
        # source is the kinetic model; the model carries its own publication
        # (the ``from`` edge), giving an honest data -> model -> article chain
        # instead of attributing raw polynomials straight to a paper.
        for tc in (
            ThermoComment.objects.filter(
                thermo__species_id__in=sp_subjects.keys(),
                kinetic_model_id__in=km_subject.keys(),
            )
            .values("thermo__species_id", "kinetic_model_id")
            .distinct()
        ):
            dst = km_subject.get(tc["kinetic_model_id"])
            for src in sp_subjects.get(tc["thermo__species_id"], ()):
                emit(src, dst, "thermoFrom")

        # (8) Reaction --kineticsFrom--> KineticModel (via KineticsComment).
        # The rate parameters were parsed from a mechanism file, so the data
        # source is the kinetic model (its publication is one hop further out,
        # via the model's own ``from`` edge).
        for kc in (
            KineticsComment.objects.filter(
                kinetics__reaction_id__in=rxn_subject.keys(),
                kinetic_model_id__in=km_subject.keys(),
            )
            .values("kinetics__reaction_id", "kinetic_model_id")
            .distinct()
        ):
            emit(
                rxn_subject.get(kc["kinetics__reaction_id"]),
                km_subject.get(kc["kinetic_model_id"]),
                "kineticsFrom",
            )

        # (9) KineticModel --usesReaction--> Reaction (via KineticsComment).
        # Mirrors (1) KM-uses-Species: makes a model's reactions -- and through
        # them their kineticsFrom rate provenance -- reachable from the model.
        for kc in (
            KineticsComment.objects.filter(
                kinetic_model_id__in=km_subject.keys(),
                kinetics__reaction_id__in=rxn_subject.keys(),
            )
            .values("kinetic_model_id", "kinetics__reaction_id")
            .distinct()
        ):
            emit(
                km_subject.get(kc["kinetic_model_id"]),
                rxn_subject.get(kc["kinetics__reaction_id"]),
                "usesReaction",
            )

        counts = defaultdict(int)
        for e in edges:
            counts[e["kind"]] += 1

        # (10) Reaction <-> Species structural links (OntoKin hasReactant /
        # hasProduct). Unlike the provenance edges above these are the reaction
        # *stoichiometry* -- which species are the reactants/products -- so a
        # reaction can be reconstructed from its species (and vice versa) in the
        # graph. Reactants have a negative stoichiometric coefficient, products a
        # positive one. Emitted to a separate sidecar so the graph can toggle the
        # reaction layer independently of the (dense) provenance overlay; an edge
        # is only kept when its reaction and species both have a prom: node.
        rxn_species_edges = []
        seen_rs = set()
        for st in (
            Stoichiometry.objects.filter(
                reaction_id__in=rxn_subject.keys(),
                species_id__in=sp_subjects.keys(),
            )
            .values("reaction_id", "species_id", "coeff")
            .iterator()
        ):
            rxn = rxn_subject.get(st["reaction_id"])
            if not rxn:
                continue
            kind = "hasReactant" if st["coeff"] < 0 else "hasProduct"
            for sp in sp_subjects.get(st["species_id"], ()):
                if not sp.startswith("prom:"):
                    continue
                key = (rxn, sp, kind)
                if key in seen_rs:
                    continue
                seen_rs.add(key)
                rxn_species_edges.append({"from": rxn, "to": sp, "kind": kind})

        rs_counts = defaultdict(int)
        for e in rxn_species_edges:
            rs_counts[e["kind"]] += 1

        self.stdout.write("Provenance edges resolved to existing SSSOM nodes:")
        for kind in (
            "uses",
            "cites",
            "contains",
            "from",
            "locatedAt",
            "usesApparatus",
            "usesReaction",
            "thermoFrom",
            "kineticsFrom",
        ):
            self.stdout.write(f"  {kind:13s} {counts[kind]}")
        self.stdout.write(f"  {'total':13s} {len(edges)}")
        self.stdout.write("Reaction <-> species structural edges:")
        for kind in ("hasReactant", "hasProduct"):
            self.stdout.write(f"  {kind:13s} {rs_counts[kind]}")
        self.stdout.write(f"  {'total':13s} {len(rxn_species_edges)}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no files written."))
            return

        json_path = Path(options["json"])
        json_path.write_text(
            json.dumps({"edges": edges, "counts": dict(counts)}, indent=2),
            encoding="utf-8",
        )
        self._write_ttl(Path(options["ttl"]), edges)
        self.stdout.write(self.style.SUCCESS(f"Wrote {json_path}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {options['ttl']}"))

        rxn_path = Path(options["reactions"])
        rxn_path.write_text(
            json.dumps(
                {"edges": rxn_species_edges, "counts": dict(rs_counts)}
            ),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {rxn_path}"))

    # -- RDF serialization ----------------------------------------------
    def _write_ttl(self, path, edges):
        """Serialize the edges as Turtle to load alongside the SSSOM graph.

        Subjects/objects are written as CURIEs (with the prefixes they use
        declared in the header) so the file is compact and human-readable; an
        endpoint whose local part cannot be represented as a Turtle name, or
        whose prefix is unknown, falls back to a full ``<IRI>``.
        """
        curie_map = self._curie_map()
        # Predicate prefixes are always available.
        header_prefixes = {
            "dcterms": "http://purl.org/dc/terms/",
            "promv": PROMV,
            "prov": PROV,
        }

        def expand(curie):
            if "://" in curie:
                return curie
            prefix, _, local = curie.partition(":")
            base = curie_map.get(prefix)
            return (base + local) if base else None

        def term(curie):
            """CURIE (local part escaped for Turtle) if the prefix is known,
            else a full <IRI>; records which prefixes were actually used."""
            if "://" not in curie:
                prefix, _, local = curie.partition(":")
                base = curie_map.get(prefix)
                if base:
                    safe = _escape_pn_local(local)
                    if safe is not None:
                        used_prefixes.add(prefix)
                        return f"{prefix}:{safe}"
            iri = expand(curie)
            return f"<{iri}>" if iri else None

        used_prefixes = set()
        body = []
        for e in edges:
            s, o = term(e["from"]), term(e["to"])
            if not s or not o:
                continue
            pred_term = e.get("predicate") or _predicate_curie(e["kind"])
            # Record predicate prefix so it is declared even though the three
            # predicate prefixes are always emitted below.
            pred_prefix = pred_term.split(":", 1)[0]
            if pred_prefix in curie_map or pred_prefix in header_prefixes:
                used_prefixes.add(pred_prefix)
            body.append(f"{s} {pred_term} {o} .")

        lines = [
            "# Prometheus provenance layer (domain relationships between SSSOM",
            "# nodes).  Load together with prometheus.sssom.ttl: shared IRIs",
            "# connect the two layers into one knowledge graph.  Generated by",
            "# `manage.py export_provenance_edges` -- do not edit by hand.",
        ]
        for prefix in sorted(used_prefixes):
            base = header_prefixes.get(prefix) or curie_map.get(prefix)
            if base:
                lines.append(f"@prefix {prefix}: <{base}> .")
        lines.append("")
        lines.extend(body)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _curie_map():
        """Read the curie_map from the SSSOM TSV header for IRI resolution."""
        tsv = MAPPINGS_DIR / "sssom" / "prometheus.sssom.tsv"
        curie_map = {}
        if not tsv.exists():
            return curie_map
        in_block = False
        pair = re.compile(r'^#\s+([\w.]+):\s+"([^"]+)"\s*$')
        for line in tsv.read_text(encoding="utf-8").splitlines():
            if line.startswith("# curie_map:"):
                in_block = True
                continue
            if in_block:
                m = pair.match(line)
                if m:
                    curie_map[m.group(1)] = m.group(2)
                elif not line.startswith("#") or line.strip() == "#":
                    break
        return curie_map
