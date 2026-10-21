"""URLconf for dereferenceable Prometheus identifiers.

These routes mirror the ``curie_map`` bases in ``mappings/prometheus.sssom.tsv``
so every minted IRI resolves. They are included at the project root *after*
``database.urls``; the integer detail routes (``species/<int:pk>`` etc.) are
matched first, and only slug IRIs (``species/H2O``, ``kineticmodel/mb-dooley``)
fall through to the resolver. ``<str:slug>`` is used so chemical names with
spaces (e.g. ``Methyl Decanoate``) resolve.
"""

from django.urls import path

from provenance import resolver

urlpatterns = [
    path("vocab/", resolver.vocab, name="prom-vocab"),
    path("vocab/<str:term>", resolver.vocab, name="prom-vocab-term"),
    path("ontology/prometheus-exp", resolver.pmtx_ontology, name="pmtx-ontology"),
    path("species/", resolver.resolve_collection, {"kind": "species"}, name="prom-species-collection"),
    path("concept/", resolver.resolve_collection, {"kind": "concept"}, name="prom-concept-collection"),
    path("reference/", resolver.resolve_collection, {"kind": "reference"}, name="prom-reference-collection"),
    path("agent/", resolver.resolve_collection, {"kind": "agent"}, name="prom-agent-collection"),
    path("institution/", resolver.resolve_collection, {"kind": "institution"}, name="prom-institution-collection"),
    path("kineticmodel/", resolver.resolve_collection, {"kind": "kineticmodel"}, name="prom-kineticmodel-collection"),
    path("dataset/", resolver.resolve_collection, {"kind": "dataset"}, name="prom-dataset-collection"),
    path("apparatus/", resolver.resolve_collection, {"kind": "apparatus"}, name="prom-apparatus-collection"),
    path("reaction/", resolver.resolve_collection, {"kind": "reaction"}, name="prom-reaction-collection"),
    path("species/<str:slug>", resolver.resolve_node, {"kind": "species"}, name="prom-species"),
    path("concept/<str:slug>", resolver.resolve_node, {"kind": "concept"}, name="prom-concept"),
    path("reference/<str:slug>", resolver.resolve_node, {"kind": "reference"}, name="prom-reference"),
    path("agent/<str:slug>", resolver.resolve_node, {"kind": "agent"}, name="prom-agent"),
    path("institution/<str:slug>", resolver.resolve_node, {"kind": "institution"}, name="prom-institution"),
    path("kineticmodel/<str:slug>", resolver.resolve_node, {"kind": "kineticmodel"}, name="prom-kineticmodel"),
    path("dataset/<str:slug>", resolver.resolve_node, {"kind": "dataset"}, name="prom-dataset"),
    path("apparatus/<str:slug>", resolver.resolve_node, {"kind": "apparatus"}, name="prom-apparatus"),
    path("reaction/<str:slug>", resolver.resolve_node, {"kind": "reaction"}, name="prom-reaction"),
]
