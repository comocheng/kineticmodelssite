# Relationships & complex queries

The API has no usage restraints beyond authentication and rate limits: you can
traverse relationships, pull related objects inline, shape responses, and combine
all of it in a single request. There are three complementary mechanisms.

## The data model at a glance

```
ExperimentDataset ──< ExperimentDatapoint ──1:1── one measurement record
   │  apparatus, file_authors, reference (Source),        (ignition-delay,
   │  common_properties                                    laminar-burning-velocity,
   └─ datapoints                                           rate-coefficient, …)
ExperimentDatapoint ── composition (Composition) ──< CompositionSpecies (species + amount)

KineticModel ── source (Source);   Species ──< Isomers ── formula (Formula) / structures; Reactions ── Kinetics
SimulationRun = KineticModel × ExperimentDataset ── result (SimulationResult) ──< DatapointResult
ModelDatasetCoverage = KineticModel × ExperimentDataset  (agreement summary)
```

## 1. Expand related objects inline — `?expand=`

By default, foreign keys come back as IDs. Add `?expand=` to pull them inline in
the same response; use a dotted path for nested expansion:

!!! note "Why expand exists"
    By default a related object is returned as just its ID. For example, an
    ignition-delay record gives `{"id": 12, "ignition_delay": 0.00042, "datapoint": 87}`,
    where `datapoint` is only the number `87`. To get that datapoint's temperature,
    pressure, and composition you would otherwise make a second request to
    `/api/experiment-datapoint/87/`, and looping over 500 records would mean 500 extra
    requests (the classic "N+1 requests" problem, slow over a network). `?expand=`
    lets you pull the related object inline in a single request, but only when you ask
    for it, so callers who just need the IDs still get small, fast responses. Only the
    fields listed below are expandable; endpoints not listed return related objects as
    IDs.

```bash
# A datapoint with its full dataset object inline
GET /api/experiment-datapoint/5/?expand=dataset

# …and the dataset's literature source too (nested)
GET /api/experiment-datapoint/5/?expand=dataset.reference

# A simulation run with both its model and dataset
GET /api/simulation-run/?expand=kinetic_model,dataset

# A species with its isomers expanded
GET /api/species/?expand=isomers
```

**Expandable fields by endpoint**

| Endpoint | Expandable |
|----------|-----------|
| `experiment-datapoint` | `dataset` |
| `experiment-dataset` | `reference` (Source) |
| `ignition-delay`, `laminar-burning-velocity`, `rate-coefficient`, `concentration-time-profile`, `jet-stirred-reactor`, `outlet-concentration`, `burner-stabilized-flame` | `datapoint` |
| `simulation-run`, `model-dataset-coverage` | `kinetic_model`, `dataset` |
| `simulation-result` | `simulation_run` |
| `datapoint-result` | `simulation_result`, `datapoint` |
| `species` | `isomers` |
| `source` | `authors` |
| `isomer` | `formula` |
| `structure` | `isomer` |

!!! tip "Performance"
    Expanding on a large list multiplies work per row. Combine `?expand=` with
    filters and pagination, or expand on detail (`/{id}/`) requests.

## 2. Filter across relationships — `__`

Relationships are traversable in filters with Django's `__` syntax:

```bash
# All datapoints in dataset 42
GET /api/experiment-datapoint/?dataset=42

# All ignition-delay measurements belonging to dataset 42
GET /api/ignition-delay/?datapoint__dataset=42

# Data containing methane (by CAS), at the datapoint or dataset level
GET /api/experiment-datapoint/?composition__species__cas=74-82-8
GET /api/experiment-dataset/?datapoints__composition__species__cas=74-82-8

# Ignition-delay points in a temperature window
GET /api/ignition-delay/?datapoint__temperature__gte=1000&datapoint__temperature__lte=1500

# Datasets from a shock tube measuring ignition delay
GET /api/experiment-dataset/?apparatus__kind=shock tube&experiment_type=ignition delay
```

Every measurement endpoint accepts `datapoint__dataset`, `datapoint__temperature`,
`datapoint__pressure`, `datapoint__equivalence_ratio`, and
`datapoint__composition__species__cas` / `…__species_name`.

## 3. Shape the response — `?fields=` / `?omit=`

```bash
# Only the fields you need
GET /api/experiment-dataset/?fields=id,experiment_type,reference_doi

# Everything except the heavy bits
GET /api/experiment-datapoint/?omit=composition
```

## Putting it together — complex query recipes

All parameters AND-combine, so one request can filter across relations, expand,
sort, and paginate:

```bash
# n-heptane (CAS 142-82-5) shock-tube ignition delays, 1000–1500 K,
# with each datapoint's conditions inline, fastest first
GET /api/ignition-delay/?datapoint__composition__species__cas=142-82-5\
&datapoint__temperature__gte=1000&datapoint__temperature__lte=1500\
&expand=datapoint&ordering=ignition_delay

# Which kinetic models reproduce dataset 42 best (current successful runs only)
GET /api/model-dataset-coverage/?dataset=42&has_successful_run=true\
&is_outdated=false&ordering=latest_error_function&expand=kinetic_model

# All datasets citing a DOI, with their bibliographic source inline
GET /api/experiment-dataset/?reference_doi=10.1016/j.combustflame.2014.03.006&expand=reference

# Per-datapoint simulated-vs-experimental comparison for a run, worst error first
GET /api/datapoint-result/?simulation_result=7&ordering=-error_value&expand=datapoint
```

See the [language examples](../examples/python.md) for these as runnable scripts.

## Following IDs (without expand)

You can always take an ID from one response and fetch it from its endpoint:
```
GET /api/kineticmodel/1/   ->  { ..., "source": 12 }
GET /api/source/12/
```

## Pagination

List responses are paginated (50 per page). Follow the `next` link until it is
`null` to page through a full result set — see the
[paging helpers](../examples/python.md) in the language examples.

## Beyond REST — ad-hoc queries

For arbitrary joins/aggregations the REST filters don't cover, the platform
provides a sandboxed, read-only **SQL console** (`livequery`) against the live
database — the right tool for one-off, fully custom analytical queries.
