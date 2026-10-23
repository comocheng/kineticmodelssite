# Kinetic models & species

These resources are the canonical model/species layer. Reads are public; writes require
an admin token.

## Endpoints & filters

| Endpoint | Useful filters / search |
|----------|-------------------------|
| `/api/kineticmodel/` | filter `prime_id`, `source`; search `model_name`, `prime_id`, `info`, `source__doi`; order `model_name` |
| `/api/species/` | filter `prime_id`, `cas_number`; search `prime_id`, `cas_number`, `hash`, `isomers__inchi` |
| `/api/reaction/` | filter `prime_id`, `reversible`; search `prime_id`, `hash` |
| `/api/isomer/` | filter `formula`; search `inchi` |
| `/api/formula/` | filter/search `formula` |
| `/api/structure/` | filter `multiplicity`; search `smiles`, `adjacency_list` |
| `/api/thermo/`, `/api/transport/`, `/api/kinetics/` | order by `id` |
| `/api/source/` | filter `publication_year`, `journal_name`, `prime_id`; search `doi`, `source_title`, `journal_name` |
| `/api/author/` | search `firstname`, `lastname` |

## Examples

Find a kinetic model by name:

```bash
curl "https://dev.omethe.us/api/kineticmodel/?search=GRI-Mech"
```

Find a species by CAS number:

```bash
curl "https://dev.omethe.us/api/species/?cas_number=74-82-8"
```

List a model with its assembled components (the detail view nests species names and
thermo/transport/kinetics comments):

```bash
curl "https://dev.omethe.us/api/kineticmodel/1/"
```

Look up the literature source behind a model:

```bash
curl "https://dev.omethe.us/api/source/?search=10.1016/j.combustflame"
```
