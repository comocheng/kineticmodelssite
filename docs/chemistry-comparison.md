# Comparing chemistry across models and sources

These features answer three questions: which models share chemistry, what RMG-database has for a reaction or species, and how sources compare as curves. All of them rest on one shared identity.

## Shared identity

The rules are the ones RMG-Py's importer uses to detect copied chemistry (`evidence_index.py`), so the site and the importer agree.

| Field | Meaning |
|---|---|
| `Structure.structure_key` | InChIKey plus multiplicity. Resonance forms share it; spin states do not. |
| `Reaction.canonical_key` | Each side's sorted species keys, smaller side first. A reaction and its reverse-written duplicate share it. |
| `Reaction.canonical_direction` | `+1` or `-1`: which way this row is written against the key. |
| `Reaction.layer` | Sub-mechanism layer of the non-collider species: `H2/O2`, `C1`, `C2`, `C3` or `C≥4` by the largest carbon count, tagged `+N`, `+S`, `+Hal`. |
| `Kinetics.rate_fingerprint` | log10 k (SI) at 500, 1000 and 1500 K and 1 bar, as written. `[]` when it cannot be evaluated. |

Two rates are identical when they belong to the same canonical reaction, are written the same way, and their fingerprints agree within 0.01 (about 2%). Two thermo polynomials are identical within 0.1% on Cp, H, S and G at 300–2000 K.

```sh
python manage.py index_chemistry            # fills what is missing; --refresh recomputes all
```

The importer fills these fields for new rows. Plain `M` third bodies are not part of reaction identity; explicit colliders (`H2 + AR = H + H + AR`) are.

## Pressure-dependent kinetics

Earlier imports dropped every PLOG, duplicate-PLOG and Chebyshev rate. RMG-Py 4 also refuses whole libraries containing a reaction with more than three products, a collider missing from the dictionary, or term-symbol adjacency lists. `TolerantKineticsLibrary` (`database/scripts/rmg_libraries.py`) skips just those reactions and logs them. To add the missing rates to imported models:

```sh
python manage.py import_missing_pdep_kinetics --dry-run
python manage.py import_missing_pdep_kinetics
```

It only adds rows; existing kinetics are untouched. Chebyshev coefficients are stored as written in the library, in its `kunits`.

## Plots

Species, thermo, reaction and kinetics pages draw Plotly charts from data computed on the server (`database/services/curves.py`).

- **Thermo** (species and thermo pages): Cp, H, S or G against T for every model polynomial and every source record, each over its own range. Identical polynomials are drawn once and labelled with every model that uses them. ATcT ΔfH°298 appears as a point with its uncertainty; group-additivity Cp tables appear as markers.
- **Rates** (reaction and kinetics pages): k against 1000/T for every rate of the reaction, over its stated temperature range (300–3000 K when none is given), in cm, mol and s units for the reaction order. Falloff, PLOG and Chebyshev rates follow a pressure selector (0.01–100 bar, limited to each fit's range). RMG-database rates are drawn dark and dashed. Rates written in reverse are listed, not plotted, since the reverse rate needs thermo.

Each chart has a values table. Colours follow a validated, colour-blind-safe order; models beyond the eighth colour are grey and grouped in the legend.

## RMG-database counterparts

```sh
python manage.py match_rmg_libraries --dry-run
python manage.py match_rmg_libraries
python manage.py classify_reaction_families        # slow; resumes where it stopped
```

`match_rmg_libraries` reads every gas-phase kinetics library and every thermo library except BurcatNS from `RMG_DATABASE_PATH`. Entries whose reaction or species is on the site become source records: `KineticsRecord(provider="rmg_library")` and `ThermoRecord(provider="rmg_thermo_library")`. Each records the RMG-database commit. `ModelLibraryOverlap` then counts, for every model and library, how many of the model's reactions (or species with thermo) the library has, and how many are identical. The model page shows the closest libraries, the reaction page lists each library entry and the models whose rate it matches exactly, and the species page lists thermo-library entries with their curves.

`classify_reaction_families` asks RMG which reaction family generates each canonical reaction, in either direction. It stores the family and template on the reaction (`-` when no family does; `?` when RMG cannot handle the species) and RMG's rate-rule estimate as `KineticsRecord(provider="rmg_family")`. As in RMG's own model generation, families that are not trees get their rate rules from their training reactions (`add_rules_from_training`, `fill_rules_by_averaging_up`), and `fix_barrier_height` turns Evans–Polanyi and Blowers–Masel rules into Arrhenius at the reaction's H298 from RMG's thermo estimates. An estimate is not a measurement; the record says so. After a change to RMG-database, `classify_reaction_families --estimates-only` recomputes the estimates without reclassifying.

`/rmg/libraries/` and `/rmg/families/` list every library and family with data on the site; each has a page with its models, its entries or reactions here, and links to the RMG website and the source file at the matched commit.

## Shared sub-mechanisms

```sh
python manage.py analyze_shared_chemistry          # rerun after imports
```

- **Pairwise overlap** (`SharedChemistry`): for every ordered pair of models and every layer, model A's reactions, how many model B also has, and how many with an identical rate.
- **Copied blocks** (`ChemistryBlock`): identical rates used by exactly the same set of models, kept when there are at least 10. The block's origin is the earliest-published model of the set. Nested blocks show a shared core and the later edits to it.
- **Lineage**: for each model and layer, the earlier-published model with the largest share of identical rates.

- **Sub-mechanisms** (`SubMechanism`, `SubMechanismVariant`): for each layer, models whose rates in that layer are mostly identical form a family, the layer's sub-mechanism (e.g. the Galway/Aramco C1 chemistry used by 16 models). Families come from average-linkage clustering on the share of identical reactions (Jaccard ≥ 0.5; on RMG-models they are the same for any threshold from 0.4 to 0.6). Layers with fewer than 5 reactions are left out. Each distinct set of rates in a family is a variant, and models with exactly the same rates share one. Variant 1 belongs to the origin, the family's earliest-published model. Each model references the variant it uses in each layer (`kinetic_model.sub_mechanism_variants`).

A sub-mechanism is named after its origin and layer until it is renamed in the admin (e.g. "Aramco C1"). The name is kept when the analysis is rerun, as long as the family keeps at least half its models.

Each copied block has a page (`/chemistry-block/<id>`) with its models and reactions. The model page has a "Shared chemistry" section, with the sub-mechanism and variant of each layer. `/submechanism/` lists every sub-mechanism by layer. `/submechanism/<id>` compares its variants: what each shares with a chosen reference variant, a heatmap of how alike they are, and every reaction with a letter per variant, where the same letter means the same rate. `/kineticmodel/compare/?a=&b=` compares two models layer by layer and lists the shared reactions whose rates differ, largest difference first. `/kineticmodel/similarity/` is a heatmap of identical rates between every pair of models, per layer; click a cell to compare that pair.
