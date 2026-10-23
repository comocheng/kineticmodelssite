# Analysis & agreement

The `analysis` endpoints expose the simulation pipeline's output: how each kinetic model
performs against each experimental dataset. All read-only.

!!! note
    User attribution (`triggered_by_user`) and server tracebacks are **excluded** from the
    public API. You see the scientific results, not internal/operational details.

## Endpoints & filters

| Endpoint | Useful filters | Notes |
|----------|----------------|-------|
| `/api/simulation-run/` | `status`, `triggered_by`, `kinetic_model`, `dataset` | one run = one (model × dataset) evaluation |
| `/api/simulation-result/` | `simulation_run` | aggregate error/deviation, T/P span, counts |
| `/api/datapoint-result/` | `temperature__gte/lte`, `pressure__gte/lte`, `success`, `error_value__gte/lte` | per-datapoint simulated vs. experimental |
| `/api/model-dataset-coverage/` | `has_successful_run`, `is_outdated`, `kinetic_model`, `dataset`, `latest_error_function__gte/lte` | coverage matrix |
| `/api/fuel-model-compatibility/` | `fuel`, `kinetic_model` | which models handle which fuels |

## Examples

Aggregate agreement for a model's runs, best first:

```bash
curl "https://dev.omethe.us/api/simulation-result/?ordering=average_error_function"
```

Per-datapoint comparison for failures only:

```bash
curl "https://dev.omethe.us/api/datapoint-result/?success=false"
```

Which datasets a model covers with a current successful run:

```bash
curl "https://dev.omethe.us/api/model-dataset-coverage/?kinetic_model=5&has_successful_run=true&is_outdated=false"
```

A `datapoint-result` item compares experiment and simulation directly:

```json
{
  "id": 10,
  "temperature": 1200.0,
  "pressure": 1013250.0,
  "experimental_ignition_delay": 0.00042,
  "simulated_ignition_delay": 0.00051,
  "error_value": 0.18,
  "deviation": 0.09,
  "success": true
}
```
