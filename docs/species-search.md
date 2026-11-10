# Species search

The species page (`/species_search/`) has one search field. Searches use local
records and do not wait for a chemical naming service.

The **PubChem** column links each species to its verified compound IDs (CIDs).
If its structures map to several records, each distinct CID is listed. “No linked
record” means no association has been saved; it does not imply absence from PubChem.

| Search | Result |
| --- | --- |
| `methane`, `CH4`, `74-82-8`, `smiles:C` | The same methane species, once names have been enriched |
| `C2H6O` | All stored species with that molecular formula, including ethanol and dimethyl ether |
| `ethanol`, `ethyl alcohol`, `CCO`, `OCC` | Ethanol records, without expanding to other formula isomers |
| `COC` | Dimethyl ether records |
| PrIMe ID, CAS number, or species database ID | Matching records |
| `InChI=...`, `isomer:123`, `structure:123` | Species associated with that identity |

Exact names take precedence over partial name matches, so `methane` does not
also return chloromethane. If no exact name is found, partial names are searched.
Equivalent SMILES are canonicalized locally, preserving stereochemistry,
isotopes, charges, and radical electrons. Augmented RMG InChIs are matched
literally so their extra electronic-state information is retained.

Some strings are both valid formulas and SMILES. A bare `CO` means the molecular
formula CO; `smiles:CO` means methanol. Use `formula:`, `smiles:`, or `name:` to
make the interpretation explicit. Standard element capitalization applies to
automatically recognized formulas; Unicode subscripts such as `CH₄` also work.
Existing bookmarked URLs using the old separate filters remain supported.

## Populate names and the structure index

Deploy the code and database migration together. In the site's Python environment:

```bash
python manage.py migrate
python manage.py enrich_species_names --index-only
python manage.py enrich_species_names --dry-run --limit 10
python manage.py enrich_species_names
```

The first command adds fields and a synonym table; the second builds the local
SMILES index for existing structures without network access. New structures saved
through the model are indexed automatically. Bulk inserts must be followed by
the indexing command. Names for existing and newly imported structures are
populated by the last command; run it after imports or from a scheduled job.

The enrichment command retrieves IUPAC names and synonyms from
[PubChem PUG-REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), using the
[IUPAC FAIR Chemistry Cookbook's structure-query approach](https://iupac.github.io/WFChemCookbook/datasources/pubchem_pugrest3.html).
Names are attached to structures, never to formulas: a formula does not identify
a unique isomer. The original formula, SMILES, augmented InChI, species hash,
and model-specific names are preserved.

Returned SMILES must match the local canonical identity before names are saved.
Unmatched, standardized-to-a-different-structure, or absent PubChem compounds keep
their existing identifiers and model names; no chemical names are invented.
Some valid PubChem compounds have no IUPAC name. Their synonyms are retained if
available; if neither is available, the lookup is marked checked and its verified
CID is saved without assigning a name. This is missing naming coverage, not a failed request.
Use `--refresh`
to check these records again later.
PubChem does not cover every combustion radical or electronic state. SMILES
alone does not encode spin multiplicity; use the stored augmented InChI or
structure ID when that distinction matters.

Requests have timeouts, retry transient failures, and are limited to four per
second per command process. Run one enrichment worker at a time. Completed
lookups are skipped on subsequent runs. Isolated API failures are logged with
the structure ID and HTTP status or error type, and the command continues with
the next structure. Failed rows are left unchanged and eligible for retry.
After five consecutive API failures the command stops; use
`--max-consecutive-errors N` to change that threshold (or `1` to fail fast).
Any run with failed lookups exits with a nonzero status after printing a summary;
previously saved progress is preserved. Rerun the command to retry unresolved
records, keeping `--refresh` if retrying a refresh run. Use `--limit N` for batches,
`--after-id N` to start after a particular structure, and `--refresh` to recheck
completed lookups (including compounds previously not found). A refresh replaces
the cached PubChem names; it does not alter imported model-specific names.

## Verification

```bash
python manage.py test database.tests.test_species_search_unit --settings=kms.test_settings
```

Tests cover formula versus exact-structure searches, stereochemistry, aliases,
legacy filters, pagination, bounded page query counts, API failures, and
resumable enrichment. API calls are mocked in automated tests.
