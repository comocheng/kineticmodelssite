# Experimental data

The ChemKED experimental-data layer is **read-only** over the API; new data is added via
the [contribution workflow](../contributing-data.md). Quantities, apparatus, authors, and
composition are nested inline, so responses carry real values (not just IDs).

## Structure

```
ExperimentDataset            (apparatus, reference, authors, common properties)
└── ExperimentDatapoint      (temperature, pressure, equivalence_ratio, composition)
    └── one measurement-type detail record, e.g.:
        ├── IgnitionDelayDatapoint
        ├── LaminarBurningVelocityMeasurementDatapoint
        ├── RateCoefficientDatapoint
        ├── ConcentrationTimeProfileMeasurementDatapoint
        ├── JetStirredReactorMeasurementDatapoint
        ├── OutletConcentrationMeasurementDatapoint
        └── BurnerStabilizedFlameSpeciationMeasurementDatapoint
```

## Key endpoints & filters

| Endpoint | Useful filters |
|----------|----------------|
| `/api/experiment-dataset/` | `experiment_type`, `reference_doi`, `reference_year__gte/lte`, `apparatus__kind`, `apparatus__mode`, `is_valid` |
| `/api/experiment-datapoint/` | `temperature__gte/lte`, `pressure__gte/lte`, `equivalence_ratio__gte/lte`, `dataset` |
| `/api/ignition-delay/` | `ignition_delay__gte/lte`, `ignition_target`, `ignition_type`, `datapoint__temperature__gte/lte` |
| `/api/laminar-burning-velocity/` | `laminar_burning_velocity__gte/lte`, `stretch__gte/lte`, `datapoint__equivalence_ratio__gte/lte` |
| `/api/composition-species/` | `species_name`, `cas`, `inchi`, `smiles`, `amount__gte/lte` (search across all) |
| `/api/apparatus/` | `kind`, `mode`, `institution`, `facility` |

## Example: ignition-delay datapoints for a high-temperature window

```bash
curl "https://dev.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1200&ordering=datapoint__temperature"
```

A response item (abridged):

```json
{
  "id": 1,
  "datapoint": 42,
  "ignition_target": "OH*",
  "ignition_type": "max",
  "ignition_delay": 0.00042,
  "ignition_delay_quantity": { "value": 0.00042, "units": "s", "uncertainty": 3e-05 }
}
```

## Finding datasets that contain a species

Use `composition-species` to locate compositions containing a species (by name, CAS,
InChI, or SMILES), then follow the composition back to its datapoints/datasets:

```bash
curl "https://dev.omethe.us/api/composition-species/?cas=74-82-8"
```

See the [language examples](../examples/python.md) for end-to-end scripts.
