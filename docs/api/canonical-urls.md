# Canonical URLs

Every record that has an identity outside this database has a canonical URL:

```
https://pr.omethe.us/id/<kind>/<key>
```

The key comes from the chemistry or from an outside identifier, never from a row number, so a
rebuild of the database gives the same URL. The API record gives it as `key` and
`canonical_url`, and `?key=` finds the record by its key.

| Kind | Key | Example |
|---|---|---|
| `species` | InChIKey and spin multiplicity of each structure (joined by `,`); `@state` for an excited state | `/id/species/XLYOFNOQVPJJNP-UHFFFAOYSA-N-1` (H2O) |
| `structure` | InChIKey and spin multiplicity; the resonance forms of a molecule share it | `/id/structure/TUJKJAMUKRIRHC-UHFFFAOYSA-N-2` (OH) |
| `reaction` | species keys of the reaction, `A+B=C+D`, and `/f` or `/r` for the direction of the record | `/id/reaction/<A>+<B>=<C>+<D>/f` |
| `kinetics` | the reaction key and a digest of the rate parameters, the collider, the efficiencies and, for a Chebyshev rate, the T and P range | `/id/kinetics/<reaction key>/<digest>` |
| `thermo` | the species key and a digest of the NASA polynomials and the reference state; the provider key for the NASA copy of a provider record | `/id/thermo/<species key>/<digest>` |
| `thermo-record` | `provider:provider ID:provider version` | `/id/thermo-record/atct:100-41-4*0:1.220` |
| `kineticmodel` | the model name (its folder in RMG-models) | `/id/kineticmodel/PCI2013/325-Husson` |
| `source` | the DOI | `/id/source/10.1016/j.combustflame.2020.01.001` |
| `person` | the ORCID iD | `/id/person/0000-0002-1825-0097` |
| `institution` | the ROR ID | `/id/institution/04t5xt781` |

A record without such an identity (a source without a DOI, a person without an ORCID iD) has
no canonical URL yet.

## Answers of the resolver

| HTTP status | When |
|---|---|
| 303 | One record has the key: the web page of the record, or its API record when the request asks for JSON (`Accept: application/json` or `?format=json`). |
| 300 | Several records have the key: a reaction key without `/f` or `/r` when both directions are records, the resonance forms of a structure, or records with the same content. The answer lists them. |
| 301 | The identity of the record changed (a corrected identification): the canonical URL of the new key. |
| 410 | The record was removed: a page that keeps what the record was, the reason and the date. |
| 404 | No record ever had the key. |

A key is never given to another record, and a key that a record had is never deleted.

## Keeping the keys current

```
python manage.py assign_record_keys            # dry run: counts what would change
python manage.py assign_record_keys --apply
python manage.py assign_record_keys --apply --kind species --kind reaction
```

Run it after an import, after a clean-up that merges or removes records, and after a rebuild.
`CANONICAL_ID_BASE` sets the base of the canonical URLs (for example a w3id.org address that
redirects here); blank gives `PUBLIC_SITE_URL` + `/id`.
