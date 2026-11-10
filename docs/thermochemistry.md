# Thermochemistry sources

Species pages compare **ATcT**, **Burcat**, and **Group Additivity** records with their source version, structure, electronic state, and provenance. Records from different providers coexist; imports do not replace a model's original thermo or silently choose a preferred source. Values are stored in SI units (J/mol and J/(mol K)).

Apply the schema update:

```sh
python manage.py migrate
```

## Backfill every species and monitor new entries

```sh
python manage.py sync_atct_catalog
python manage.py enrich_species_thermo
python manage.py enrich_species_thermo --status
```

The backfill creates one durable job per **structure and source**, covering every species that uses that structure. It scans the complete local structure set, matches the cached ATcT catalog and configured Burcat library, and estimates group-additivity thermo where supported. ATcT's catalog is retrieved in pages with the API's `%` wildcard search. The downloader checks the reported total and uniqueness before atomically replacing the previous snapshot. The source version is taken from each API record; it may differ from the version advertised on the ATcT website.

Automatic ATcT matching requires the same molecular graph, charge and multiplicity, a single unqualified gas-phase candidate, and at most one unpaired electron. Explicit electronic terms, excited-state descriptors, stereochemistry/isotopes unsupported by the importer, multiple plausible matches, and unresolved identities remain **Needs review**. It does not select an isomer by formula alone. Preferred formulas such as `NH3` and `H3N` are compared by elemental composition.

Candidates are found by the structure's canonical SMILES. If ATcT has none, the structure's RMG resonance forms are tried, because ATcT and the models can draw a species differently (benzyl, vinoxy, N2O). Aromatic and Kekulé rings count as the same graph. A resonance match links the record to a structure drawn as ATcT draws it, if one exists, and otherwise to the structure that was looked up. It never creates structures or species. A few ATcT records have SMILES that RDKit cannot parse (NO2 is written `O=[N]=O`). For these, the record's InChI supplies the structure, and the provenance says so. CAS numbers are not used: few local structures have one, and PubChem's CAS synonyms can belong to a different ATcT molecule.

Run the dedicated worker and monitor as supervised services:

```sh
celery -A kms worker --queues=thermo --pool=solo --concurrency=1 --loglevel=INFO
python manage.py monitor_species_thermo
```

The monitor uses Celery Beat to discover/process new entries every **five minutes**, with a nightly ATcT catalog refresh at 02:15 in Celery's configured timezone. The existing application-wide `celery -A kms beat` includes the same schedules; use **one** scheduler arrangement. `monitor_species_thermo` schedules only thermochemistry tasks, leaving other application jobs alone. The worker must consume the `thermo` queue. Under a process supervisor, restart these services after deploying code changes; a local launch does not install an operating-system startup service.

New structures enqueue database work on save without network calls or a Redis dependency in the request. Periodic scanning also catches bulk imports that bypass Django signals. Work claims use row locks and leases; successful writes and completion are transactional. Crashed-worker leases become eligible after 30 minutes. Requests and individual structure processing have time limits, while batches have Celery time limits. A provider access failure pauses that source's pending queue rather than sending thousands of repeated failing requests. Other sources continue.

Useful controls:

```sh
python manage.py enrich_species_thermo --enqueue-only
python manage.py enrich_species_thermo --limit 100
python manage.py enrich_species_thermo --provider atct --retry-failed
python manage.py enrich_species_thermo --provider atct --refresh
```

`--limit` counts source/structure jobs, not species. A normal rerun resumes due work; `--retry-failed` also requeues blocked, unsupported, and review outcomes. `--refresh` rechecks all selected-source jobs, including completed and no-match results. Successful and no-match jobs are eligible for another check after 30 days. A changed catalog downloaded by the scheduled task requeues ATcT jobs immediately; after a manual catalog sync, run `--provider atct --refresh` to do the same. Unsupported scientific cases are not silently retried forever or given fabricated data.

Monitor progress with `--status`, Django admin's **Thermo enrichment jobs**, or the read-only `/api/thermo-enrichment/?provider=atct&status=blocked` endpoint. Species pages show only the source records and the provenance of the sidebar enthalpy, not lookup status. `Available` means a matching source record or validated estimate exists; `No match` refers only to the configured source coverage (BurcatNS remains a subset). Failed/blocked lookups are distinct from confirmed no matches.

Configuration:

| Variable | Purpose |
|---|---|
| `THERMO_RMG_DATABASE_PATH` | RMG database used by the background worker; falls back to `RMG_DATABASE_PATH`/RMG's installation |
| `THERMO_ATCT_SNAPSHOT_PATH` | Catalog cache; defaults to `var/thermo/atct-catalog.json`; set to an empty string for individual live lookups |
| `THERMO_BURCAT_LIBRARY` | Optional trusted structure-resolved Burcat library replacing the default BurcatNS subset |
| `THERMO_ENRICHMENT_BATCH_SIZE` | Jobs per scheduled batch; default 100 |
| `THERMO_JOB_TIMEOUT_SECONDS` | Per-structure processing limit on supported Unix main-thread workers; default 120 |
| `ATCT_USER_AGENT` | Request identification; defaults to the configuration verified with the installed ATcT Python client |

`--database-path` and `--atct-snapshot` override the worker's source configuration for a foreground backfill. Download failures preserve the last verified catalog. A missing catalog is reported as a blocked source; the scheduled task attempts to bootstrap it automatically.

## ATcT reference values

The integration uses the published [ATcT API client contract](https://github.com/Dbross/atct). Configure `ATCT_API_BASE_URL` if your endpoint differs from `https://atct.anl.gov/api/v1`, and optionally set `ATCT_API_KEY` in the environment (Bearer authentication). Requests have timeouts and bounded retries for temporary failures.

Import a record by its exact ATcT identifier:

```sh
python manage.py import_atct_thermo --atct-id '74-82-8*0' --multiplicity 1 --state-label 'ground state' --dry-run
python manage.py import_atct_thermo --atct-id '74-82-8*0' --multiplicity 1 --state-label 'ground state'
```

Review the electronic state and multiplicity against the selected ATcT record. The API does not reliably provide these fields; the command requires an explicit declaration and rejects a multiplicity inconsistent with its SMILES-derived graph. It accepts explicitly gas-phase records with usable structures, cross-checks formula, charge and supplied InChI, and refuses stereospecific/isotopic records that RMG's graph identity cannot preserve. Formula or CAS alone never establishes a match.

Each import preserves ATcT ID, thermochemical-network version, original response, formation enthalpies at 0 and 298.15 K, and the reported uncertainty. An ATcT enthalpy alone does **not** determine a NASA polynomial: heat capacities and an entropy reference are also needed. The ATcT record itself therefore has no NASA link. It does not assume independent uncertainties or calculate reaction uncertainties from them.

## ATcT-constrained RMG thermo

When the same isomer and spin also has a Burcat or group-additivity NASA polynomial, the site derives an **ATcT-constrained RMG thermo** record from it. RMG's `NASA.change_base_enthalpy` moves the source polynomial so that H(298.15 K) equals the ATcT value; Cp(T) and S(T) stay exactly the source's. Each derived record links to both its ATcT record and its Cp/S source, and stores the size of the shift plus checks: H(298.15 K) within 1 J/mol of ATcT, and Cp and S unchanged across the fit range. It carries **no uncertainty**. ATcT's uncertainty applies to ΔfH°298 only and does not establish the accuracy of Cp(T), S(T) or the polynomial at other temperatures.

The enrichment worker derives these records whenever an ATcT match or a new Burcat or group-additivity record arrives. To backfill or rebuild them:

```sh
python manage.py derive_atct_thermo --dry-run
python manage.py derive_atct_thermo
```

Species pages list each derived record beside its ATcT record, with the shift that was applied. A large shift means the Cp/S source does not describe the molecule well. Group additivity misses ozone by 240 kJ/mol, for example, so treat that record's Cp and S with the same caution. The worker has no derived-thermo jobs; the provider appears only on records.

If live access is unavailable, add `--input-file /path/to/record.json` to import a previously retrieved API JSON object with the same ID. Offline imports receive an explicit provenance note; the local timestamp denotes import time. A Cloudflare challenge or HTTP 401/403 stops live imports without changing saved records. Use your authorized API endpoint/key configuration for live refreshes.

## Burcat NASA polynomials

Set `RMG_DATABASE_PATH` to your RMG-database checkout, or pass `--database-path`. The installed RMG default database location is used if the configured path is absent and that installation includes the data.

```sh
python manage.py import_burcat_thermo --database-path /path/to/RMG-database --dry-run
python manage.py import_burcat_thermo --database-path /path/to/RMG-database
```

The default is RMG's **BurcatNS**, a curated sulfur/nitrogen subset, **not the complete Burcat database**. Its entry count depends on your database version. A trusted, structure-resolved RMG Burcat library can be provided with `--library /path/to/library.py`. RMG loads Python library files as code; use trusted local files. `--label` (repeatable) and `--limit` select a smaller batch.

Native Burcat thermofiles cannot be matched safely by formula alone; convert them into an RMG library with verified adjacency lists before importing. The importer requires two valid, adjoining NASA7 intervals supporting the site's 298.15 K reference. It preserves library and entry notes, coefficients, reference, and a content digest. Burcat entries are not automatically marked as ATcT-derived; check each entry's provenance. Unknown reference pressure remains unspecified.

## RMG group additivity

```sh
python manage.py estimate_species_thermo --database-path /path/to/RMG-database --structure-id 123 --dry-run
python manage.py estimate_species_thermo --database-path /path/to/RMG-database --structure-id 123
python manage.py estimate_species_thermo --database-path /path/to/RMG-database --all --limit 100
```

`--structure-id` can be repeated; `--after-id` supports continuing a bounded batch. The estimator loads only RMG group data, generates resonance structures, and applies the molecular symmetry entropy correction. It does not fall back to library thermo and label it as a group estimate.

Records retain RMG version, group-file content digest, group comments, symmetry number, original Cp table and reference values, and fit diagnostics. RMG's tabulated H298/S298 reference is 298 K; comparison values on the site are evaluated at 298.15 K. NASA fits cover 200–3000 K, including extrapolation beyond the original tabulated Cp temperatures. They must have positive finite sampled Cp, at most 5% relative deviation at the original Cp points, and differences no greater than 500 J/mol in H and 1 J/(mol K) in S at 298.15 K. Unsupported structures or failed fits are reported without saving a fabricated record. These are estimates, with no invented uncertainty.

All commands are idempotent for a given source ID and version. Changed versions create separate records. Batches preserve successful records, report failures, and exit nonzero if any item failed. `--dry-run` validates with transaction rollback and saves no records.

## API

`GET /api/thermo-record/` exposes source records; filter with `provider=atct`, `provider=burcat`, or `provider=group_additivity`, plus `species`, `structure`, `external_id`, or `source_version`. Each record includes its linked canonical species and structure. The species page also shows source records for the species' exact isomers, so pre-existing resonance collections can display applicable references. It also shows records matched by its structures' lookups, including records attached to a resonance form under another isomer. The endpoint is read-only. `/api/thermo/` includes `provider_record` for linked NASA polynomials.

## Verification

Run `database.tests.test_thermo_sources_unit` under the project's test settings. Set `KMS_THERMO_TEST_DATABASE=/path/to/RMG-database` to additionally exercise real Burcat imports and a propane group-additivity fit in the isolated test database.
