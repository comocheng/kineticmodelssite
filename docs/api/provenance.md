# Provenance & FAIR metadata

These endpoints tell you where a record comes from and how it connects to other
databases. They are read-only and public. Curators change them through the Django admin
and management commands, not through the API.

## Provenance (`tags: provenance`)

| Endpoint | Description | Filters | `?search=` |
|----------|-------------|---------|------------|
| `/api/institution/` | Institutions, with their ROR ID | `country`, `parent` | name, ROR ID, country |
| `/api/person/` | Persons, with their ORCID and affiliation | `affiliation` | names, ORCID |
| `/api/license/` | Licenses, with their SPDX ID | | SPDX ID, name |
| `/api/external-identifier/` | Identifiers of a record in other schemes (InChI, InChIKey) | `scheme`, `value`, `content_type`, `object_id`, `is_primary` | value |
| `/api/semantic-mapping/` | SSSOM mappings from Prometheus terms to terms of other vocabularies | `subject_id`, `object_id`, `predicate_id`, `mapping_set_id`, `species`, `source`, `experiment_dataset`, `kinetic_model`, `institution`, `person` | subject and object IDs and labels |

### Find a species from its InChIKey

An external identifier points to its record with `content_type` and `object_id`. For a
species, `object_id` is the ID that `/api/species/` uses.

```bash
curl "https://pr.omethe.us/api/external-identifier/?scheme=inchikey&value=VNWKTOKETHGBQD-UHFFFAOYSA-N"
```

```json
{
  "count": 1,
  "results": [
    {
      "scheme": "inchikey",
      "value": "VNWKTOKETHGBQD-UHFFFAOYSA-N",
      "uri": "https://www.inchi-trust.org/inchikey/VNWKTOKETHGBQD-UHFFFAOYSA-N",
      "is_primary": true,
      "object_id": 13
    }
  ]
}
```

### Find the same species in other databases

`?species=` takes the species ID. Each mapping gives the other database's identifier in
`object_id`.

```bash
curl "https://pr.omethe.us/api/semantic-mapping/?species=13"
```

| `subject_id` | `predicate_id` | `object_id` |
|--------------|----------------|-------------|
| `prom:CH4` | `skos:exactMatch` | `inchikey:VNWKTOKETHGBQD-UHFFFAOYSA-N` |
| `prom:CH4` | `skos:exactMatch` | `pubchem.compound:297` |
| `prom:CH4` | `skos:exactMatch` | `CHEBI:16183` |
| `prom:CH4` | `skos:exactMatch` | `chembl:CHEMBL17564` |

## FAIR metadata (`tags: metadata`)

These endpoints give a record as JSON-LD (schema.org, PROV and the Prometheus ontology),
for harvesters such as Google Dataset Search and for FAIR validators.

| Endpoint | Description |
|----------|-------------|
| `/api/metadata/` | The data catalog (`schema:DataCatalog`) |
| `/api/source/{id}/metadata/` | A literature source |
| `/api/kineticmodel/{id}/metadata/` | A kinetic model (`prom:KineticModel`, `ontokin:ReactionMechanism`) |
| `/api/experiment-dataset/{id}/metadata/` | An experimental dataset |

```bash
curl "https://pr.omethe.us/api/kineticmodel/1/metadata/"
```
