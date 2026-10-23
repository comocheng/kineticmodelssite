"""drf-spectacular postprocessing hooks.

- ``add_field_examples`` gives schema fields representative, type- and
  choice-accurate ``example`` values so ReDoc/Swagger render realistic response
  samples (instead of ``"string"`` / ``0``). Values are derived from the field
  type and, for choice fields, from the actual enum; only clearly-named fields
  get domain values, and genuinely ambiguous fields are left to the UI so we
  never show a wrong value.
- ``fix_pagination_urls`` sets each list endpoint's ``next``/``previous`` example
  to that endpoint's real path (not DRF's ``api.example.org`` placeholder).
- ``add_code_samples`` injects ``x-codeSamples`` (cURL/Python/R/MATLAB/JS/Java).

Registered via ``SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"]`` (keep the default
enum hook first).
"""

from django.conf import settings

TOKEN_PLACEHOLDER = "<your-api-token>"


def _base_url():
    servers = (getattr(settings, "SPECTACULAR_SETTINGS", {}) or {}).get("SERVERS") or []
    if servers and servers[0].get("url"):
        return servers[0]["url"].rstrip("/")
    return "http://localhost:8000"


# ---------------------------------------------------------------------------
# Multi-language request code samples (x-codeSamples)
# ---------------------------------------------------------------------------
def _curl(method, url, has_body):
    parts = [f"curl -X {method}", f'-H "Authorization: Token {TOKEN_PLACEHOLDER}"']
    if has_body:
        parts.append('-H "Content-Type: application/json"')
        parts.append("-d '{ }'")
    parts.append(f'"{url}"')
    return " \\\n  ".join(parts)


def _python(method, url, has_body):
    fn = method.lower()
    lines = [
        "import requests",
        "",
        f'url = "{url}"',
        f'headers = {{"Authorization": "Token {TOKEN_PLACEHOLDER}"}}',
        "",
    ]
    if has_body:
        lines.append(f"resp = requests.{fn}(url, headers=headers, json={{}})")
    else:
        lines.append(f"resp = requests.{fn}(url, headers=headers)")
    lines += ["resp.raise_for_status()", "print(resp.json())"]
    return "\n".join(lines)


def _r(method, url, has_body):
    lines = [
        "library(httr2)",
        "",
        f'resp <- request("{url}") |>',
        f'  req_headers(Authorization = "Token {TOKEN_PLACEHOLDER}") |>',
    ]
    if has_body:
        lines.append("  req_body_json(list()) |>")
    if method != "GET":
        lines.append(f'  req_method("{method}") |>')
    lines.append("  req_perform()")
    lines.append("resp_body_json(resp)")
    return "\n".join(lines)


def _matlab(method, url, has_body):
    lines = [f'opts = weboptions("HeaderFields", ["Authorization" "Token {TOKEN_PLACEHOLDER}"]);']
    if method == "GET":
        lines.append(f'data = webread("{url}", opts);')
    else:
        lines.append(f'opts.RequestMethod = "{method.lower()}";')
        body = "struct()" if has_body else "[]"
        lines.append(f'data = webwrite("{url}", {body}, opts);')
    return "\n".join(lines)


def _javascript(method, url, has_body):
    header = f'"Authorization": "Token {TOKEN_PLACEHOLDER}"'
    if has_body:
        header += ', "Content-Type": "application/json"'
    lines = [
        f'const res = await fetch("{url}", {{',
        f'  method: "{method}",',
        f"  headers: {{ {header} }},",
    ]
    if has_body:
        lines.append("  body: JSON.stringify({}),")
    lines += ["});", "const data = await res.json();", "console.log(data);"]
    return "\n".join(lines)


def _java(method, url, has_body):
    body_pub = (
        'HttpRequest.BodyPublishers.ofString("{}")'
        if has_body
        else "HttpRequest.BodyPublishers.noBody()"
    )
    lines = [
        "HttpClient client = HttpClient.newHttpClient();",
        "HttpRequest request = HttpRequest.newBuilder()",
        f'    .uri(URI.create("{url}"))',
        f'    .header("Authorization", "Token {TOKEN_PLACEHOLDER}")',
    ]
    if has_body:
        lines.append('    .header("Content-Type", "application/json")')
    lines += [
        f'    .method("{method}", {body_pub})',
        "    .build();",
        "HttpResponse<String> response = client.send(",
        "    request, HttpResponse.BodyHandlers.ofString());",
        "System.out.println(response.body());",
    ]
    return "\n".join(lines)


_GENERATORS = [
    ("shell", "cURL", _curl),
    ("python", "Python", _python),
    ("r", "R", _r),
    ("matlab", "MATLAB", _matlab),
    ("javascript", "JavaScript", _javascript),
    ("java", "Java", _java),
]

_METHODS = {"get", "post", "put", "patch", "delete"}


def add_code_samples(result, generator, request, public):
    """Inject ``x-codeSamples`` into every operation."""
    base = _base_url()
    for path, path_item in (result.get("paths") or {}).items():
        url = f"{base}{path}"
        for method, operation in path_item.items():
            if method.lower() not in _METHODS or not isinstance(operation, dict):
                continue
            m = method.upper()
            has_body = method.lower() in {"post", "put", "patch"}
            operation["x-codeSamples"] = [
                {"lang": lang, "label": label, "source": gen(m, url, has_body)}
                for lang, label, gen in _GENERATORS
            ]
    return result


# ---------------------------------------------------------------------------
# Field-accurate response examples
# ---------------------------------------------------------------------------
# Representative values for fields whose meaning is unambiguous from the name.
# Matched by exact (lower-cased) field name to avoid mismatches.
_STR_EXAMPLES = {
    "inchi": "InChI=1S/CH4/h1H4",
    "smiles": "C",
    "cas": "74-82-8",
    "cas_number": "74-82-8",
    "doi": "10.1016/j.combustflame.2014.03.006",
    "reference_doi": "10.1016/j.combustflame.2014.03.006",
    "file_doi": "10.24388/x10100000",
    "prime_id": "s00000123",
    "model_name": "GRI-Mech 3.0",
    "species_name": "methane",
    "chem_name": "methane",
    "formula": "CH4",
    "journal_name": "Combustion and Flame",
    "source_title": "Comprehensive H2/O2 kinetic model for high-pressure combustion",
    "adjacency_list": "1 C u0 p0 c0 {2,S} {3,S} {4,S} {5,S}",
    "institution": "Northeastern University",
    "facility": "Shock Tube",
    "firstname": "Jane",
    "lastname": "Doe",
    "experiment_type": "ignition delay",
}
_NUM_EXAMPLES = {
    "temperature": 1000.0,
    "environment_temperature": 1000.0,
    "min_temperature": 800.0,
    "max_temperature": 1800.0,
    "pressure": 101325.0,
    "min_pressure": 101325.0,
    "max_pressure": 1013250.0,
    "equivalence_ratio": 1.0,
    "ignition_delay": 0.00042,
    "first_stage_ignition_delay": 0.001,
    "laminar_burning_velocity": 0.38,
    "stretch": 100.0,
    "residence_time": 1.5,
    "distance": 0.01,
    "flow_rate": 5.0,
    "coeff": 1.0,
    "amount": 0.21,
    "reaction_order": 2,
    "multiplicity": 1,
    "reference_year": 2014,
    "publication_year": 2004,
    "reference_volume": 161,
}


def _set_examples_on_component(comp):
    if not isinstance(comp, dict):
        return
    # Enum component -> first valid choice (so choice fields render a real value).
    if comp.get("enum") and "example" not in comp:
        comp["example"] = comp["enum"][0]
        return
    props = comp.get("properties")
    if not isinstance(props, dict):
        return
    for pname, p in props.items():
        if not isinstance(p, dict) or "example" in p:
            continue
        # Leave references / unions / arrays for the UI to compose from their
        # own schema (this is also how nested objects and paginated ``results``
        # get populated).
        if any(k in p for k in ("$ref", "allOf", "oneOf", "anyOf")):
            continue
        lname = pname.lower()
        t = p.get("type")
        if p.get("enum"):
            p["example"] = p["enum"][0]
        elif t == "integer":
            p["example"] = _NUM_EXAMPLES.get(lname, 1)
        elif t == "number":
            p["example"] = _NUM_EXAMPLES.get(lname, 1.0)
        elif t == "boolean":
            p["example"] = True
        elif t == "string":
            if lname in _STR_EXAMPLES:
                p["example"] = _STR_EXAMPLES[lname]
            # Unrecognized free-text / ambiguous strings (e.g. units): leave to
            # the UI so we never assert a wrong value.


def add_field_examples(result, generator, request, public):
    """Attach representative examples to schema components."""
    for comp in ((result.get("components") or {}).get("schemas") or {}).values():
        _set_examples_on_component(comp)
    return result


def fix_pagination_urls(result, generator, request, public):
    """Point each list endpoint's next/previous example at its real path."""
    host = _base_url()
    netloc = host.split("://", 1)[-1]
    schemas = (result.get("components") or {}).get("schemas") or {}

    for path, item in (result.get("paths") or {}).items():
        get = item.get("get") if isinstance(item, dict) else None
        if not isinstance(get, dict):
            continue
        try:
            ref = get["responses"]["200"]["content"]["application/json"]["schema"].get("$ref")
        except (KeyError, TypeError, AttributeError):
            ref = None
        if not ref:
            continue
        comp = schemas.get(ref.rsplit("/", 1)[-1])
        props = comp.get("properties") if isinstance(comp, dict) else None
        if not isinstance(props, dict) or "results" not in props:
            continue
        if "next" in props:
            props["next"]["example"] = f"{host}{path}?page=2"
        if "previous" in props:
            props["previous"]["example"] = None

    # Safety net: rewrite any remaining api.example.org host left in the schema.
    def walk(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if isinstance(val, str) and "api.example.org" in val:
                    node[key] = val.replace("http://api.example.org", host).replace(
                        "api.example.org", netloc
                    )
                else:
                    walk(val)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    walk(result)
    return result


# ---------------------------------------------------------------------------
# Materialized response examples (so Swagger UI renders them too)
# ---------------------------------------------------------------------------
# ReDoc synthesizes a response sample from per-property ``example`` values, but
# Swagger UI's auto-generator does not render nested ``$ref`` objects the same
# way.  Building a concrete example object and attaching it at the response
# media-type level makes both renderers show the same corrected sample.

_FALLBACK = {
    "integer": 0,
    "number": 0.0,
    "boolean": True,
    "string": "string",
}

# Realistic (unit, value) for a nested ValueWithUnit, inferred from the name of
# the parent property it hangs off. Ordered most-specific first so that, e.g.,
# ``first_stage_ignition_delay`` and ``pressure_rise`` match before
# ``ignition_delay`` / ``pressure``.
_QUANTITY_UNITS = (
    ("equivalence_ratio", ("", 1.0)),
    ("temperature", ("K", 1000.0)),
    ("pressure_rise", ("bar/ms", 0.5)),
    ("pressure", ("atm", 1.0)),
    ("first_stage_ignition_delay", ("us", 1000.0)),
    ("ignition_delay", ("us", 420.0)),
    ("laminar_burning_velocity", ("cm/s", 38.0)),
    ("burning_velocity", ("cm/s", 38.0)),
    ("residence_time", ("s", 1.5)),
    ("flow_rate", ("sccm", 5.0)),
    ("distance", ("cm", 1.0)),
)


def _apply_unit_hint(pname, value):
    """Give a materialized nested ValueWithUnit realistic units, in place."""
    if not isinstance(value, dict) or "units" not in value:
        return
    low = pname.lower()
    for key, (unit, val) in _QUANTITY_UNITS:
        if key in low:
            value["units"] = unit
            if "value" in value:
                value["value"] = val
            if "value_text" in value:
                value["value_text"] = f"{val} {unit}".strip()
            return


def _example_from_schema(node, schemas, seen):
    """Build a concrete example value from a (possibly $ref) schema node."""
    if not isinstance(node, dict):
        return None

    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in seen:  # guard against recursive components
            return {}
        return _example_from_schema(schemas.get(name, {}), schemas, seen | {name})

    if "example" in node:
        return node["example"]

    if node.get("allOf"):
        merged = {}
        for sub in node["allOf"]:
            val = _example_from_schema(sub, schemas, seen)
            if isinstance(val, dict):
                merged.update(val)
        return merged
    for key in ("oneOf", "anyOf"):
        if node.get(key):
            return _example_from_schema(node[key][0], schemas, seen)

    if node.get("enum"):
        return node["enum"][0]

    t = node.get("type")
    if t == "object" or "properties" in node:
        obj = {}
        for pname, p in (node.get("properties") or {}).items():
            child = _example_from_schema(p, schemas, seen)
            _apply_unit_hint(pname, child)
            obj[pname] = child
        return obj
    if t == "array":
        item = _example_from_schema(node.get("items") or {}, schemas, seen)
        return [item] if item is not None else []
    if t == "string" and node.get("format") == "date-time":
        return "2024-01-01T00:00:00Z"
    return _FALLBACK.get(t)


def add_response_examples(result, generator, request, public):
    """Attach a materialized example to each JSON response (renderer-agnostic).

    Runs after ``add_field_examples`` and ``fix_pagination_urls`` so the
    per-property and pagination examples are already in place.
    """
    schemas = (result.get("components") or {}).get("schemas") or {}
    for path_item in (result.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in (operation.get("responses") or {}).values():
                content = response.get("content") if isinstance(response, dict) else None
                media = content.get("application/json") if isinstance(content, dict) else None
                if not isinstance(media, dict) or "example" in media:
                    continue
                schema = media.get("schema")
                if not isinstance(schema, dict):
                    continue
                example = _example_from_schema(schema, schemas, frozenset())
                if example is not None:
                    media["example"] = example
    return result


_FLEX_PARAMS = [
    {
        "name": "expand",
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
        "description": (
            "Comma-separated related fields to expand inline instead of returning "
            "their IDs, e.g. `?expand=dataset` or nested `?expand=dataset.reference`. "
            "Expandable fields are documented per endpoint."
        ),
    },
    {
        "name": "fields",
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
        "description": "Comma-separated subset of fields to return (sparse fieldset).",
    },
    {
        "name": "omit",
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
        "description": "Comma-separated fields to omit from the response.",
    },
]


def add_flex_params(result, generator, request, public):
    """Document the drf-flex-fields expand/fields/omit query params on GET operations."""
    for path_item in (result.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        get = path_item.get("get")
        if not isinstance(get, dict):
            continue
        params = get.setdefault("parameters", [])
        existing = {p.get("name") for p in params if isinstance(p, dict)}
        for fp in _FLEX_PARAMS:
            if fp["name"] not in existing:
                params.append(dict(fp))
    return result


# ---------------------------------------------------------------------------
# Ontology / linked-data context
# ---------------------------------------------------------------------------
# Namespaces used by the JSON-LD metadata endpoints (api.fair_metadata) and the
# ontology artifacts (prometheus_chemked_ontology.ttl, prometheus-exp.ttl).
_ONTOLOGY_CONTEXT = {
    "prom": "https://dev.omethe.us/ontology/prometheus#",
    "chemked": "https://dev.omethe.us/ontology/chemked#",
    "pmtx": "https://dev.omethe.us/ontology/prometheus-exp#",
    "ontokin": "http://www.theworldavatar.com/ontology/ontokin/OntoKin.owl#",
    "ontochemexp": "http://www.theworldavatar.com/ontology/ontochemexp/OntoChemExp.owl#",
    "ontospecies": "http://www.theworldavatar.com/ontology/ontospecies/OntoSpecies.owl#",
    "qudt": "http://qudt.org/schema/qudt/",
    "prov": "http://www.w3.org/ns/prov#",
    "dcterms": "http://purl.org/dc/terms/",
    "schema": "https://schema.org/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


def add_ontology_context(result, generator, request, public):
    """Advertise the ontology namespaces backing the JSON-LD metadata endpoints.

    Surfaces an ``x-ontologyContext`` block in ``info`` so API consumers can
    resolve the ``prom:``/``chemked:``/``ontokin:`` terms used by the
    ``<resource>/<pk>/metadata/`` linked-data documents.
    """
    result.setdefault("info", {})["x-ontologyContext"] = dict(_ONTOLOGY_CONTEXT)
    return result
