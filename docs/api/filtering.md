# Filtering, search & ordering

Every list endpoint supports three query mechanisms. They compose freely.

## Field filters

Filter by exact value or by range using `__` lookups:

| Lookup | Example | Meaning |
|--------|---------|---------|
| exact | `?experiment_type=ignition delay` | equals |
| `__gte` / `__lte` | `?temperature__gte=1000&temperature__lte=1500` | range |
| `__icontains` | `?reference_journal__icontains=combustion` | case-insensitive contains |

### Worked examples

Ignition-delay datapoints measured between 1000 K and 1500 K:

```bash
curl "https://dev.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1000&datapoint__temperature__lte=1500"
```

Datapoints near stoichiometric (φ ≈ 1) above 10 atm (≈ 1.0e6 Pa):

```bash
curl "https://dev.omethe.us/api/experiment-datapoint/?equivalence_ratio__gte=0.9&equivalence_ratio__lte=1.1&pressure__gte=1000000"
```

Datasets for a given paper:

```bash
curl "https://dev.omethe.us/api/experiment-dataset/?reference_doi=10.1016/j.combustflame.2014.03.006"
```

Completed simulation runs for a model:

```bash
curl "https://dev.omethe.us/api/simulation-run/?status=completed&kinetic_model=5"
```

!!! note "Choice fields are validated"
    Fields with fixed choices (e.g. `experiment_type`, `status`) reject invalid values
    with `400` and list the valid options — a quick way to discover allowed values.

## Search

`?search=` runs a case-insensitive search across the endpoint's text fields:

```bash
curl "https://dev.omethe.us/api/composition-species/?search=methanol"
curl "https://dev.omethe.us/api/kineticmodel/?search=GRI"
```

## Ordering

`?ordering=field` (ascending) or `?ordering=-field` (descending):

```bash
curl "https://dev.omethe.us/api/ignition-delay/?ordering=ignition_delay"
curl "https://dev.omethe.us/api/experiment-datapoint/?ordering=-temperature"
```

## Discovering the parameters

The exact filter/search/ordering parameters for each endpoint are documented in the
[OpenAPI schema](../reference.md) and appear as inputs in [Swagger UI](../reference.md).
