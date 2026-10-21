# ChemKED Database App

This app provides Django models for storing ChemKED experimental data (currently focused on ignition-delay datasets) with support for complex structures like common-properties, time histories, and RCM data.

## What’s modeled

- **Datasets** (`ExperimentDataset`) representing one ChemKED YAML file
- **Datapoints** (`ExperimentDatapoint`) representing individual measurements
- **Compositions** (`Composition`) with normalized species rows
- **Ignition delay datapoints** (`IgnitionDelayDatapoint`) for ignition-delay-specific fields
- **Flame speed datapoints** (`FlameSpeedDatapoint`) placeholder for laminar flame speed datasets
- **Species profile datapoints** (`SpeciesProfileDatapoint`) placeholder for species-vs-time datasets
- **Species thermo** (`SpeciesThermo`) stored as a separate model (no JSON field)
- **Common properties** (`CommonProperties`) shared across a dataset
- **RCM data** (`RCMData`) for compression parameters
- **Time histories** (`TimeHistory`) and **Volume histories** (`VolumeHistory`)
- **Composition species** (`CompositionSpecies`) for normalized species queries

## Notes

- Numeric values are stored in SI unless noted in the source YAML.
- Large time-series arrays are stored as JSON for efficiency.
- Composition is available in both JSON form and normalized species rows.
- Use `chemked_database/import_dispatcher.py` to attach the correct experiment-type extension model.
- Quantities can also be stored with units via `ValueWithUnit` to mirror PyKED's value-unit schema.

## Tests

Run the app tests from the project root:

```bash
python3.9 manage.py test chemked_database
```

## Importer

Use the management command to import ChemKED YAML files:

```bash
python manage.py sync_chemked --path /path/to/ChemKED-database
```

`--path` defaults to the `CHEMKED_DATABASE_PATH` setting (environment variable of the
same name; default `../ChemKED-database` next to the project).

Options:
- `--files PATH [PATH ...]` to import only these repo-relative files
- `--limit N` to import only the first N files
- `--dry-run` to scan without writing to the database

The command exits with an error if any file is missing or fails to import. Importing a
file again replaces its datapoints.

### Duplicate data and target folder

`chemked_database/repo_check.py` indexes the committed YAML files of the
`CHEMKED_DATABASE_PATH` clone (cached by git blob, so only new files are read again).
The web upload, the REST API (`/api/contribute/`) and git pull requests use it:

- **Duplicate:** a file whose experiment type, apparatus kind, reactions and datapoints
  (common properties merged in) equal those of a committed file, in any folder and under
  any name. File authors, file version, reference metadata, comments and formatting do not
  count. A file with the same *name* in another folder is not a duplicate: one paper
  often gives one file per fuel (for example `butanol/Beeckmann_2014/…` and
  `ethanol/Beeckmann_2014/…`).
- **Target folder:** the fuel folder that holds files with the same fuel species (and the
  same NOx content, for the `*_NOx` folders), else the folder for the same main fuel, else
  a folder named after the fuel. Below it: the subfolder of files from the same paper
  (same DOI), else an existing or new `Author_Year` subfolder.

The web upload preview shows the folder and any matching file with a diff; the pull
request then updates the matching file instead of adding a copy. For git pull requests,
the `pyked-ci-validate` workflow on the runner runs `manage.py ci_check_chemked_repo`,
which posts the check-run *ChemKED Duplicate and Folder Check*: duplicate data is a
failure, a new file outside the expected folder is a warning. Without a clone, the web
upload falls back to the GitHub API and only matches exact bytes or a file name that is
used once in the repository.

### Ingest after merge

When a pull request that changes YAML files is merged into ChemKED-database `master`,
its `ingest-on-merge.yml` workflow sends a `chemked-ingest` repository dispatch to this
repository. `.github/workflows/chemked-ingest.yml` then runs on the self-hosted runner:
it pulls the clone at `CHEMKED_DATABASE_PATH` and runs `sync_chemked --files` for the
merged files. Requirements:

- ChemKED-database secret `DISPATCH_TOKEN`: a token that can send repository dispatches
  to this repository (optional variables `PYTECK_REPO_OWNER`, `PYTECK_REPO_NAME` name it).
- Runner `kms.env`: database credentials and `CHEMKED_DATABASE_PATH`, pointing to a
  ChemKED-database clone on the runner host that can `git pull --ff-only`.
- The workflow must be on this repository's default branch; GitHub runs
  `repository_dispatch` workflows from the default branch only.

To backfill any missing composition links:

```bash
python manage.py backfill_compositions
```

To infer missing SMILES/atomic composition from existing InChI values:

```bash
python manage.py backfill_species_identifiers
```
