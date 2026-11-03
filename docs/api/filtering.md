# Filtering, search & ordering

Every list endpoint supports three query mechanisms. They compose freely.

## Field filters

Filter by exact value or by range using `__` lookups:

| Lookup | Example | Meaning |
|--------|---------|---------|
| exact | `?experiment_type=ignition delay` | equals |
| `__gte` / `__lte` | `?temperature__gte=1000&temperature__lte=1500` | range |
| `__icontains` | `?reference_journal__icontains=combustion` | case-insensitive contains |
| `__in` | `?dataset__in=3,7,9` | one of the comma-separated values |
| `__isnull` | `?equivalence_ratio__isnull=true` | the field has no value |
| `has_` | `?has_volume_history=true` | the record has related rows (`false`: has none) |

Numeric filters take SI values: K, Pa, s. A record is listed once, however many related
rows match a filter (for example a dataset with many datapoints that contain the species).

### Worked examples

Ignition-delay datapoints measured between 1000 K and 1500 K:

```bash
curl "https://pr.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1000&datapoint__temperature__lte=1500"
```

Datapoints near stoichiometric (φ ≈ 1) above 10 atm (≈ 1.0e6 Pa):

```bash
curl "https://pr.omethe.us/api/experiment-datapoint/?equivalence_ratio__gte=0.9&equivalence_ratio__lte=1.1&pressure__gte=1000000"
```

Datasets for a given paper:

```bash
curl "https://pr.omethe.us/api/experiment-dataset/?reference_doi=10.1016/j.combustflame.2014.03.006"
```

Completed simulation runs for a model:

```bash
curl "https://pr.omethe.us/api/simulation-run/?status=completed&kinetic_model=5"
```

!!! note "Choice fields are validated"
    Fields with fixed choices (e.g. `experiment_type`, `status`) reject invalid values
    with `400` and list the valid options — a quick way to discover allowed values.

!!! note "Unknown parameters are errors"
    A list request with a parameter that the endpoint does not support answers `400` with
    `unknown_parameters` and `allowed_parameters`, so a misspelt `presure__gte` or an
    unsupported `pressure__gt` cannot silently return the whole table. An unknown
    `ordering` field answers `400` with `allowed_ordering`.

## Species in a mixture

The datapoint endpoints, the measurement-type endpoints (`/api/ignition-delay/` and the
others) and `/api/experiment-dataset/` select by the mixture of a datapoint: its own
composition, or the common-properties composition of its dataset when it has none.

| Parameter | Value |
|-----------|-------|
| `species` | ID of a species record from `/api/species/` (the same ID selects kinetic models) |
| `inchi` | InChI of a component, with or without the `InChI=` prefix |
| `cas` | CAS number of a component |

`species` and `inchi` compare standard InChIs: RMG's `/u` (unpaired electrons) and `/lp`
(lone pairs) layers are dropped, so the triplet O2 record (`InChI=1S/O2/c1-2/u1,2`) finds
the O2 of the experiments (`1S/O2/c1-2`). A standard InChI has no spin layer, so records
that differ only in their spin, such as triplet O2 and singlet O2 ("O2X"), select the same
components. An excited-state record (OH*) selects only the components linked to it.

Repeat a parameter to require every value in the same mixture. NH3/H2 blends:

```bash
curl "https://pr.omethe.us/api/experiment-datapoint/?inchi=1S/H3N/h1H3&inchi=1S/H2/h1H"
```

An InChI can contain commas, so these parameters are repeated, not comma-separated.

## Conditions on one datapoint

On `/api/experiment-dataset/`, `species`, `inchi`, `cas` and the ranges
`temperature__gte/lte`, `pressure__gte/lte` and `equivalence_ratio__gte/lte` apply to one
datapoint: a dataset is listed when one of its datapoints meets every condition given.
Ignition-delay datasets with NH3 and a datapoint at 10 atm (1013250 Pa) or more:

```bash
curl "https://pr.omethe.us/api/experiment-dataset/?experiment_type=ignition+delay&inchi=1S/H3N/h1H3&pressure__gte=1013250"
```

The datapoints of those datasets, in one request:

```bash
curl "https://pr.omethe.us/api/experiment-datapoint/?dataset__in=910,912,916&page_size=1000"
```

## Search

`?search=` runs a case-insensitive search across the endpoint's text fields:

```bash
curl "https://pr.omethe.us/api/composition-species/?search=methanol"
curl "https://pr.omethe.us/api/kineticmodel/?search=GRI"
```

## Ordering

`?ordering=field` (ascending) or `?ordering=-field` (descending). The measurement-type
endpoints can also be ordered by `datapoint__temperature`, `datapoint__pressure` and
`datapoint__equivalence_ratio`:

```bash
curl "https://pr.omethe.us/api/ignition-delay/?ordering=ignition_delay"
curl "https://pr.omethe.us/api/experiment-datapoint/?ordering=-temperature"
```

## Pages

List responses come in pages of 50 records with `count`, `next` and `previous`.
`?page_size=` asks for up to 1000 records on a page; `?page=` selects the page.

## Discovering the parameters

The exact filter/search/ordering parameters for each endpoint are documented in the
[OpenAPI schema](../reference.md) and appear as inputs in [Swagger UI](../reference.md).
