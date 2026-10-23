"""Export the data layer: structural links from species/reaction SSSOM nodes to
their thermodynamic, transport and kinetic *value records*.

The SSSOM file is an identifier crosswalk and the provenance sidecar carries the
entity-to-entity relationships, but neither says *where the numbers live*.  This
command emits that missing layer: each species links to its thermo/transport
records and each reaction links to its rate-parameter records, where every
record is a dereferenceable IRI (its existing ``/thermo/<pk>`` ``/transport/<pk>``
``/kinetics/<pk>`` detail page, which content-negotiates to RDF).  Following one
of those IRIs returns the actual NASA polynomials / Lennard-Jones parameters /
Arrhenius coefficients, so the published file stays lean (links + record type +
data provenance) while the literals remain one hop away.

  * ``prom:X      pmtx:hasThermo         promthermo:<pk>``  (+ ``a pmtx:ThermoData``)
  * ``prom:X      pmtx:hasTransport      promtrans:<pk>``   (+ ``a pmtx:TransportData``)
  * ``promrxn:X   pmtx:hasRateParameters promkin:<pk>``     (+ ``a pmtx:RateParameters``)

Each record also carries ``prov:wasDerivedFrom promkm:<model>`` for the kinetic
model(s) it was parsed from -- the same honest data -> model -> article chain the
provenance layer uses.  A link is only emitted when its species/reaction already
has an SSSOM node, so the data layer overlays cleanly on the mapping set.

Read-only against the database; idempotent (overwrites the sidecar).
"""

import json
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from database.models import Kinetics, Thermo, Transport
from database.models.kinetic_model import (
    KineticsComment,
    ThermoComment,
    TransportComment,
)
from provenance.models import SemanticMapping

MAPPINGS_DIR = Path(__file__).resolve().parents[4] / "mappings"
DEFAULT_TTL = MAPPINGS_DIR / "rdf" / "prometheus.data.ttl"
DEFAULT_JSON = MAPPINGS_DIR / "sssom" / "prometheus.data.json"

PMTX = "https://dev.omethe.us/ontology/prometheus-exp#"
PROV = "http://www.w3.org/ns/prov#"

# (record kind) -> (link predicate CURIE, record type CURIE, record prefix)
RECORD = {
    "thermo": ("pmtx:hasThermo", "pmtx:ThermoData", "promthermo"),
    "transport": ("pmtx:hasTransport", "pmtx:TransportData", "promtrans"),
    "kinetics": ("pmtx:hasRateParameters", "pmtx:RateParameters", "promkin"),
}

# Sub-delimiter characters a Turtle PN_LOCAL may contain only when escaped.
_PN_LOCAL_ESC = set("~!$&'()*+,;=/?#@-._")
_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")


def _escape_pn_local(local):
    """Escape a CURIE local part into a valid Turtle PN_LOCAL.

    Species names carry characters (``* ( ) = , # @`` and percent escapes) that
    are legal in a CURIE only when escaped, so emit the escaped CURIE instead of
    a verbose full ``<IRI>``.  Letters, digits and ``_`` pass through; ``-``/``.``
    are kept except where the grammar forbids them unescaped (leading ``-``/``.``,
    trailing ``.``); existing ``%HH`` percent-encoding is preserved; remaining
    sub-delimiters are backslash-escaped.  Returns ``None`` if a character cannot
    be represented (caller then falls back to a full ``<IRI>``).
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


def _fmt(value):
    """Render a number compactly, or None if missing/non-numeric."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return f"{num:.6g}"


def _thermo_summary(t):
    """Human-readable value lines for a thermo record (NASA polynomials)."""
    lines = []
    if t.enthalpy_formation is not None:
        lines.append(f"\u0394Hf = {_fmt(t.enthalpy_formation)} J/mol")
    if t.reference_temp is not None:
        lines.append(f"Reference T = {_fmt(t.reference_temp)} K")
    for coeffs, tmin, tmax, name in (
        (t.coeffs_poly1, t.temp_min_1, t.temp_max_1, "Low"),
        (t.coeffs_poly2, t.temp_min_2, t.temp_max_2, "High"),
    ):
        if coeffs:
            rng = f"[{_fmt(tmin)}\u2013{_fmt(tmax)} K]"
            lines.append(
                f"NASA {name} {rng}: " + ", ".join(_fmt(c) for c in coeffs)
            )
    return lines


def _transport_summary(tr):
    """Human-readable value lines for a transport record (Lennard-Jones)."""
    lines = []
    for label, val, unit in (
        ("Well depth \u03b5/k", tr.potential_well_depth, "K"),
        ("Collision diameter \u03c3", tr.collision_diameter, "\u00c5"),
        ("Dipole moment", tr.dipole_moment, "debye"),
        ("Polarizability", tr.polarizability, "\u00c5\u00b3"),
        ("Rotational relaxation", tr.rotational_relaxation, ""),
    ):
        if val is not None:
            lines.append(f"{label} = {_fmt(val)}{(' ' + unit) if unit else ''}")
    return lines


def _kinetics_summary(kin):
    """Human-readable value lines for a kinetics record (rate parameters)."""
    data = kin.raw_data or {}
    lines = []
    rtype = data.get("type")
    if rtype:
        lines.append(f"Type: {rtype}")
    if data.get("a_si") is not None:
        lines.append(f"A = {_fmt(data.get('a_si'))} {data.get('a_units') or ''}".rstrip())
    if data.get("n") is not None:
        lines.append(f"n = {_fmt(data.get('n'))}")
    if data.get("e_si") is not None:
        lines.append(f"Ea = {_fmt(data.get('e_si'))} J/mol")
    if kin.min_temp is not None or kin.max_temp is not None:
        lines.append(f"T range: {_fmt(kin.min_temp)}\u2013{_fmt(kin.max_temp)} K")
    return lines


class Command(BaseCommand):
    help = (
        "Export the data layer: species/reaction SSSOM nodes linked to their "
        "dereferenceable thermo/transport/kinetics value records."
    )

    def add_arguments(self, parser):
        parser.add_argument("--ttl", default=str(DEFAULT_TTL))
        parser.add_argument("--json", default=str(DEFAULT_JSON))
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report record counts without writing the sidecar.",
        )

    # -- node resolution -------------------------------------------------
    def _anchors(self):
        """species_id -> prom: CURIE and reaction_id -> promrxn: CURIE."""
        sp_anchor = {}
        rxn_anchor = {}
        km_subject = {}
        for r in SemanticMapping.objects.filter(
            species__isnull=False, subject_id__startswith="prom:"
        ).values("species_id", "subject_id"):
            sp_anchor.setdefault(r["species_id"], r["subject_id"])
        for r in SemanticMapping.objects.filter(reaction__isnull=False).values(
            "reaction_id", "subject_id"
        ):
            rxn_anchor.setdefault(r["reaction_id"], r["subject_id"])
        for r in SemanticMapping.objects.filter(kinetic_model__isnull=False).values(
            "kinetic_model_id", "subject_id"
        ):
            km_subject[r["kinetic_model_id"]] = r["subject_id"]
        return sp_anchor, rxn_anchor, km_subject

    @staticmethod
    def _model_map(comment_model, record_attr, record_ids, km_subject):
        """record_id -> sorted promkm: CURIEs for the model(s) it came from."""
        out = defaultdict(set)
        rows = comment_model.objects.filter(
            **{f"{record_attr}__in": record_ids},
            kinetic_model_id__in=km_subject.keys(),
        ).values(record_attr, "kinetic_model_id")
        for r in rows:
            km = km_subject.get(r["kinetic_model_id"])
            if km:
                out[r[record_attr]].add(km)
        return {k: sorted(v) for k, v in out.items()}

    # -- main ------------------------------------------------------------
    def handle(self, *args, **options):
        sp_anchor, rxn_anchor, km_subject = self._anchors()

        triples = []
        used = set()
        curie_map = self._curie_map()

        # Parallel graph-overlay sidecar (raw CURIEs, no Turtle escaping): the
        # record nodes + their species/reaction and model edges, consumed by
        # mappings/sssom_graph.py as the "Data records" overlay.
        data_nodes = {}  # record CURIE -> record kind
        data_edges = []  # {"from", "to", "kind"}
        data_values = {}  # record CURIE -> [human-readable value lines]

        def term(curie):
            prefix, _, local = curie.partition(":")
            base = curie_map.get(prefix) or {"pmtx": PMTX, "prov": PROV}.get(prefix)
            if base:
                safe = _escape_pn_local(local)
                if safe is not None:
                    used.add(prefix)
                    return f"{prefix}:{safe}"
            return f"<{base}{local}>" if base else None

        def link(node_curie, record_kind, record_id, models):
            pred, rtype, prefix = RECORD[record_kind]
            s = term(node_curie)
            rec_curie = f"{prefix}:{record_id}"
            rec = term(rec_curie)
            if not s or not rec:
                return False
            triples.append(f"{s} {pred} {rec} .")
            triples.append(f"{rec} a {rtype} .")
            data_nodes[rec_curie] = record_kind
            data_edges.append(
                {"from": node_curie, "to": rec_curie, "kind": record_kind}
            )
            for m in models:
                mo = term(m)
                if mo:
                    triples.append(f"{rec} prov:wasDerivedFrom {mo} .")
                    data_edges.append(
                        {"from": rec_curie, "to": m, "kind": "derivedFrom"}
                    )
            return True

        counts = defaultdict(int)

        # Species --hasThermo--> thermo record
        thermo_rows = list(
            Thermo.objects.filter(species_id__in=sp_anchor.keys())
        )
        thermo_models = self._model_map(
            ThermoComment, "thermo_id", [t.id for t in thermo_rows], km_subject
        )
        for t in thermo_rows:
            if link(
                sp_anchor[t.species_id],
                "thermo",
                t.id,
                thermo_models.get(t.id, ()),
            ):
                counts["thermo"] += 1
                summary = _thermo_summary(t)
                if summary:
                    data_values[f"promthermo:{t.id}"] = summary

        # Species --hasTransport--> transport record
        transport_rows = list(
            Transport.objects.filter(species_id__in=sp_anchor.keys())
        )
        transport_models = self._model_map(
            TransportComment,
            "transport_id",
            [t.id for t in transport_rows],
            km_subject,
        )
        for t in transport_rows:
            if link(
                sp_anchor[t.species_id],
                "transport",
                t.id,
                transport_models.get(t.id, ()),
            ):
                counts["transport"] += 1
                summary = _transport_summary(t)
                if summary:
                    data_values[f"promtrans:{t.id}"] = summary

        # Reaction --hasRateParameters--> kinetics record
        kinetics_rows = list(
            Kinetics.objects.filter(reaction_id__in=rxn_anchor.keys())
        )
        kinetics_models = self._model_map(
            KineticsComment,
            "kinetics_id",
            [k.id for k in kinetics_rows],
            km_subject,
        )
        for k in kinetics_rows:
            if link(
                rxn_anchor[k.reaction_id],
                "kinetics",
                k.id,
                kinetics_models.get(k.id, ()),
            ):
                counts["kinetics"] += 1
                summary = _kinetics_summary(k)
                if summary:
                    data_values[f"promkin:{k.id}"] = summary

        self.stdout.write("Data-layer records linked to existing SSSOM nodes:")
        for kind in ("thermo", "transport", "kinetics"):
            self.stdout.write(f"  {kind:10s} {counts[kind]}")
        self.stdout.write(f"  {'triples':10s} {len(triples)}")
        self.stdout.write(f"  {'values':10s} {len(data_values)}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no file written."))
            return

        self._write_ttl(Path(options["ttl"]), triples, used, curie_map)
        self.stdout.write(self.style.SUCCESS(f"Wrote {options['ttl']}"))
        self._write_json(Path(options["json"]), data_nodes, data_edges, data_values)
        self.stdout.write(self.style.SUCCESS(f"Wrote {options['json']}"))

    # -- serialization ---------------------------------------------------
    @staticmethod
    def _write_ttl(path, triples, used, curie_map):
        header_prefixes = {"pmtx": PMTX, "prov": PROV}
        # pmtx (link predicate + record type) and prov (wasDerivedFrom) appear in
        # every record, so they are always declared.
        used = set(used) | {"pmtx", "prov"}
        lines = [
            "# Prometheus data layer: species/reaction SSSOM nodes linked to",
            "# their dereferenceable thermo/transport/kinetics value records.",
            "# Each record IRI content-negotiates to its numeric literals.",
            "# Generated by `manage.py export_data_layer` -- do not edit by hand.",
        ]
        for prefix in sorted(used):
            base = header_prefixes.get(prefix) or curie_map.get(prefix)
            if base:
                lines.append(f"@prefix {prefix}: <{base}> .")
        lines.append("")
        lines.extend(triples)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _write_json(path, data_nodes, data_edges, data_values):
        """Graph-overlay sidecar: record nodes + species/reaction and model edges.

        Mirrors ``prometheus.provenance.json`` so ``sssom_graph.py`` can render the
        data layer as a toggleable overlay.  CURIEs are raw (no Turtle escaping);
        the graph resolves them via the SSSOM ``curie_map``.  ``values`` maps each
        record CURIE to its human-readable value lines so the graph can display
        the actual numbers on demand.
        """
        payload = {
            "nodes": [
                {"id": curie, "kind": kind} for curie, kind in sorted(data_nodes.items())
            ],
            "edges": data_edges,
            "values": data_values,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

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
