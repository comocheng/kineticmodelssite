# Kinetic models & species

These resources are the canonical model/species layer. Reads are public; writes require
an admin token.

## Endpoints & filters

| Endpoint | Useful filters / search |
|----------|-------------------------|
| `/api/kineticmodel/` | filter `prime_id`, `source`, `species` (a species ID; repeat for models with every species given); search `model_name`, `prime_id`, `info`, `source__doi`; order `model_name` |
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
curl "https://pr.omethe.us/api/kineticmodel/?search=GRI-Mech"
```

Find a species by CAS number:

```bash
curl "https://pr.omethe.us/api/species/?cas_number=74-82-8"
```

Find the models that contain a set of species: look up each species record (by InChI, CAS
number or name), then pass its `id` as `species`, once per species. A model is returned only
if its species list contains every species given:

```bash
curl "https://pr.omethe.us/api/species/?search=InChI=1S/H3N/h1H3"   # -> id of NH3
curl "https://pr.omethe.us/api/kineticmodel/?species=<H2 id>&species=<NH3 id>"
```

List a model with its assembled components (the detail view nests species names and
thermo/transport/kinetics comments):

```bash
curl "https://pr.omethe.us/api/kineticmodel/1/"
```

Each kinetics comment gives the model's own arrow (`reversible`). Where the model's CHEMKIN line
gives an explicit reverse rate (`REV / A n Ea /`), `reverse_rate` holds it: `{"terms": [...]}`,
one Arrhenius rate (A per mole, in cm) or `null` per rate term, with the CHEMKIN line and its text.
Without it, the reverse rate comes from thermochemistry. The CHEMKIN download writes it as `REV`,
and the Cantera download as a second, irreversible reaction.

Look up the literature source behind a model:

```bash
curl "https://pr.omethe.us/api/source/?search=10.1016/j.combustflame"
```
