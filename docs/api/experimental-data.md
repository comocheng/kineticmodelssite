# Experimental data

The ChemKED experimental-data layer is **read-only** over the API; new data is added via
the [contribution workflow](../contributing-data.md). Quantities, apparatus, authors, and
composition are nested inline, so responses carry real values (not just IDs).

## Structure

```
ExperimentDataset            (apparatus, reference, authors, common properties)
└── ExperimentDatapoint      (temperature, pressure, equivalence_ratio, composition)
    └── one measurement-type detail record:
        ├── IgnitionDelayDatapoint
        ├── LaminarBurningVelocityMeasurementDatapoint
        ├── RateCoefficientDatapoint
        └── SpeciationMeasurementDatapoint   (reactor conditions, time-shift)
            ├── IndependentVariable          (columns of the profile rows)
            ├── ConcentrationProfile         (species, units, rows, uncertainty)
            └── AuxiliaryProfile             (e.g. temperature against distance)
```

The three ChemKED experiment types are `ignition delay`, `laminar burning velocity
measurement` and `speciation measurement`, as in PyKED. A speciation measurement covers jet
stirred reactors, flow reactors, burner stabilized flames and shock tubes (filter on the
apparatus kind); ReSpecTh's four speciation types convert to it. Every quantity has the
file's value and unit in `<field>_quantity` and its SI value in `<field>`.

## Key endpoints & filters

| Endpoint | Useful filters |
|----------|----------------|
| `/api/experiment-dataset/` | `experiment_type(__in)`, `species`, `inchi`, `cas`, `temperature__gte/lte`, `pressure__gte/lte`, `equivalence_ratio__gte/lte` (on one datapoint), `reference_doi`, `reference_year__gte/lte`, `apparatus__kind`, `apparatus__mode`, `is_valid`, `id__in`, `has_time_histories`, `has_volume_history`, `has_rcm_data`, `has_license` |
| `/api/experiment-datapoint/` | `temperature__gte/lte`, `pressure__gte/lte`, `equivalence_ratio__gte/lte`, `species`, `inchi`, `cas`, `dataset(__in)`, `has_time_histories`, `has_volume_history`, `has_rcm_data` |
| `/api/ignition-delay/` | `ignition_delay__gte/lte`, `ignition_target`, `ignition_type`, `has_ignition_type`, `has_pressure_rise`, `species`, `inchi`, `cas`, `datapoint__temperature__gte/lte`, `datapoint__dataset(__in)` |
| `/api/laminar-burning-velocity/` | `laminar_burning_velocity__gte/lte`, `stretch__gte/lte`, `datapoint__equivalence_ratio__gte/lte` |
| `/api/speciation-measurement/` | `datapoint__dataset__apparatus__kind`, `independent_variables__name`, `concentration_profiles__species__species_name`, `concentration_profiles__species__inchi`, `residence_time__gte/lte`, `reactor_volume__gte/lte`, `flow_rate__gte/lte` |
| `/api/concentration-profile/` | `species__species_name`, `species__inchi`, `quantity_units`, `measurement__datapoint__dataset`, `measurement__datapoint__dataset__apparatus__kind` |
| `/api/auxiliary-profile/` | `profile_type`, `independent_name`, `measurement__datapoint__dataset` |
| `/api/time-history/` | `datapoint(__in)`, `datapoint__dataset(__in)`, `history_type(__in)` |
| `/api/volume-history/` | `datapoint(__in)`, `datapoint__dataset(__in)` |
| `/api/rcm-data/` | `datapoint(__in)`, `datapoint__dataset(__in)`, `compressed_temperature__gte/lte`, `compressed_pressure__gte/lte` |
| `/api/composition-species/` | `species_name`, `cas`, `inchi`, `smiles`, `amount__gte/lte` (search across all) |
| `/api/apparatus/` | `kind`, `mode`, `institution`, `facility` |

## Example: ignition-delay datapoints for a high-temperature window

```bash
curl "https://pr.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1200&ordering=datapoint__temperature"
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

## Example: species measured in jet stirred reactors

```bash
curl "https://pr.omethe.us/api/concentration-profile/?species__species_name=CH2O&measurement__datapoint__dataset__apparatus__kind=jet%20stirred%20reactor"
```

A response item (abridged). Each row of `values` holds one value per independent variable of
the measurement, then the amount, then optionally its uncertainty:

```json
{
  "id": 7,
  "measurement": 3,
  "species": { "species_name": "CH2O", "inchi": "1S/CH2O/c1-2/h1H2", "composition": null, "amount": null },
  "quantity_units": "mole fraction",
  "values": [[800.0, 1.2e-05], [825.0, 3.1e-05]],
  "uncertainty_type": "relative",
  "uncertainty": 0.1,
  "uncertainty_sourcetype": "reported"
}
```

`/api/speciation-measurement/{id}/` gives the measurement with its independent variables
(in column order), reactor conditions and all profiles; `?expand=datapoint` adds pressure,
temperature and inlet composition.

## Finding datasets that contain a species

`species` (a species record ID), `inchi` or `cas` select the datasets with a datapoint whose
mixture contains the species, including a mixture given once in the common properties.
Repeat the parameter for blends, and add ranges that the same datapoint must meet (see
[filtering](filtering.md#conditions-on-one-datapoint)):

```bash
curl "https://pr.omethe.us/api/experiment-dataset/?cas=74-82-8"
curl "https://pr.omethe.us/api/experiment-dataset/?experiment_type=ignition+delay&inchi=1S/H3N/h1H3&inchi=1S/H2/h1H&pressure__gte=1013250"
```

`composition-species` lists the components themselves (by name, CAS, InChI, or SMILES).

See the [language examples](../examples/python.md) for end-to-end scripts.
