"""JSON-LD builders for the FAIR metadata endpoints.

Each builder turns a platform record into a schema.org / PROV / Prometheus-
ontology JSON-LD document so external harvesters (Google Dataset Search,
ontology tools, FAIR validators) can consume our records as linked data.

The base URL is derived from ``SPECTACULAR_SETTINGS["SERVERS"]`` (via
``api.schema_hooks._base_url``) rather than hardcoded, so the ``@id`` URIs match
whatever host the schema is served from.
"""

from api.schema_hooks import _base_url

# JSON-LD @context shared by every document. Namespaces mirror the ontology
# artifacts (prometheus_chemked_ontology.ttl, prometheus-exp.ttl) and the SSSOM
# curie map.
CONTEXT = {
    "schema": "https://schema.org/",
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "prom": "https://dev.omethe.us/ontology/prometheus#",
    "chemked": "https://dev.omethe.us/ontology/chemked#",
    "pmtx": "https://dev.omethe.us/ontology/prometheus-exp#",
    "ontokin": "http://www.theworldavatar.com/ontology/ontokin/OntoKin.owl#",
    "ontochemexp": "http://www.theworldavatar.com/ontology/ontochemexp/OntoChemExp.owl#",
    "ontospecies": "http://www.theworldavatar.com/ontology/ontospecies/OntoSpecies.owl#",
    "qudt": "http://qudt.org/schema/qudt/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


def _doi_uri(value):
    return f"https://doi.org/{value}" if value else ""


def _license_uri(obj):
    lic = getattr(obj, "license", None)
    return lic.uri if lic else ""


def _isoformat(dt):
    return dt.isoformat() if dt else ""


def _person_node(author):
    """Build a schema:Person node from any author row.

    Prefers the canonical ``provenance.Person`` link (ORCID + affiliation) and
    falls back to the row's own ``name``/``orcid`` when not yet linked.
    """
    person = getattr(author, "person", None)
    if person is not None:
        name = person.name
        orcid = person.orcid_uri
        affiliation = (
            {
                "@type": "schema:Organization",
                "schema:name": person.affiliation.name,
                "schema:identifier": person.affiliation.ror_uri,
            }
            if person.affiliation
            else None
        )
    else:
        name = getattr(author, "name", None) or str(author)
        raw_orcid = getattr(author, "orcid", "") or ""
        orcid = (
            raw_orcid
            if raw_orcid.startswith("http") or not raw_orcid
            else f"https://orcid.org/{raw_orcid}"
        )
        affiliation = None

    node = {
        "@type": ["prov:Person", "schema:Person"],
        "schema:name": name,
    }
    if orcid:
        node["schema:identifier"] = orcid
    if affiliation:
        node["schema:affiliation"] = affiliation
    return node


def source_jsonld(source):
    base = _base_url()
    return {
        "@context": CONTEXT,
        "@id": f"{base}/api/source/{source.pk}/",
        "@type": ["prom:Source", "ontokin:Reference", "schema:ScholarlyArticle"],
        "schema:name": source.source_title,
        "prom:doi": source.doi,
        "schema:identifier": _doi_uri(source.doi) or source.prime_id,
        "schema:url": source.url,
        "schema:datePublished": source.publication_year,
        "schema:isPartOf": source.journal_name,
        "schema:pagination": source.page_numbers,
        "schema:license": _license_uri(source),
        "schema:dateCreated": _isoformat(source.created_at),
        "schema:dateModified": _isoformat(source.updated_at),
        "schema:author": [_person_node(a) for a in source.authors.all()],
    }


def kinetic_model_jsonld(model):
    base = _base_url()
    return {
        "@context": CONTEXT,
        "@id": f"{base}/api/kineticmodel/{model.pk}/",
        "@type": [
            "prom:KineticModel",
            "ontokin:ReactionMechanism",
            "schema:SoftwareSourceCode",
        ],
        "schema:name": model.model_name,
        "schema:identifier": model.prime_id,
        "schema:description": model.info,
        "schema:license": _license_uri(model),
        "schema:version": model.version,
        "schema:codeRepository": model.repository_url,
        "schema:encodingFormat": model.model_format,
        "schema:citation": _doi_uri(model.zenodo_doi),
        "schema:dateCreated": _isoformat(model.created_at),
        "schema:dateModified": _isoformat(model.updated_at),
        "prom:hasSource": (
            f"{base}/api/source/{model.source_id}/" if model.source_id else ""
        ),
    }


def experiment_dataset_jsonld(dataset):
    base = _base_url()
    apparatus = dataset.apparatus
    institution_node = None
    if apparatus is not None and getattr(apparatus, "institution_ref", None):
        inst = apparatus.institution_ref
        institution_node = {
            "@type": "schema:Organization",
            "schema:name": inst.name,
            "schema:identifier": inst.ror_uri,
        }
    return {
        "@context": CONTEXT,
        "@id": f"{base}/api/experiment-dataset/{dataset.pk}/",
        "@type": ["chemked:ExperimentDataset", "pmtx:ExperimentDataset", "schema:Dataset"],
        "schema:name": dataset.short_name,
        "chemked:experimentType": dataset.experiment_type,
        "prom:filePath": dataset.chemked_file_path,
        "prom:doi": dataset.file_doi or dataset.reference_doi,
        "schema:identifier": _doi_uri(dataset.file_doi or dataset.reference_doi),
        "schema:license": _license_uri(dataset),
        "schema:distribution": (
            {"@type": "schema:DataDownload", "schema:contentUrl": dataset.data_repository_url}
            if dataset.data_repository_url
            else None
        ),
        "schema:includedInDataCatalog": f"{base}/api/metadata/",
        "schema:dateCreated": _isoformat(dataset.created_at),
        "schema:dateModified": _isoformat(dataset.updated_at),
        "schema:provider": institution_node,
        "prom:hasContributor": [_person_node(a) for a in dataset.file_authors.all()],
    }


def catalog_jsonld():
    base = _base_url()
    return {
        "@context": CONTEXT,
        "@id": f"{base}/api/metadata/",
        "@type": "schema:DataCatalog",
        "schema:name": "Prometheus Kinetic Models Database",
        "schema:url": base,
        "schema:description": (
            "FAIR combustion-kinetics cyberinfrastructure: canonical species, "
            "reactions, kinetic models, experimental datasets, and simulation results."
        ),
        "schema:license": "https://spdx.org/licenses/MIT",
        "schema:documentation": f"{base}/docs/",
        "schema:distribution": [
            {
                "@type": "schema:DataDownload",
                "schema:encodingFormat": "application/json",
                "schema:contentUrl": f"{base}/api/",
            },
            {
                "@type": "schema:DataDownload",
                "schema:encodingFormat": "application/vnd.oai.openapi",
                "schema:contentUrl": f"{base}/api/schema/",
            },
        ],
    }
