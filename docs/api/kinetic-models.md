# Kinetic models & species

These resources are the canonical model/species layer. Reads are public; writes require
an admin token.

## Endpoints & filters

| Endpoint | Useful filters / search |
|----------|-------------------------|
| `/api/kineticmodel/` | filter `id__in`, `prime_id`, `source`, `species` (a species ID; repeat for models with every species given); search `model_name`, `prime_id`, `info`, `source__doi`; order `model_name`; `fields`/`omit` (for example `fields=id,model_name` leaves out the long species, thermo and rate lists) |
| `/api/species/` | filter `inchi` (exact; see below), `multiplicity`, `has_electronic_state`, `electronic_state`, `kinetic_model`, `id__in`, `prime_id`, `cas_number`, `isomers__formula`; search `prime_id`, `cas_number`, `hash`, `isomers__inchi` (substring) |
| `/api/reaction/` | filter `species` (repeat: every species given), `kinetic_model`, `canonical_key` (both directions), `layer`, `id__in`, `prime_id`, `reversible`; search `prime_id`, `hash` |
| `/api/isomer/` | filter `formula`; search `inchi` |
| `/api/formula/` | filter/search `formula` |
| `/api/structure/` | filter `multiplicity`; search `smiles`, `adjacency_list` |
| `/api/thermo/` | filter `species`, `species__in`, `kinetic_model`, `reference` (`true`: polynomials fitted to reference records; `false`: model entries), `id__in`; order by `id` |
| `/api/kinetics/` | filter `reaction`, `reaction__in`, `canonical_key` (both directions), `species` (repeat: every species given), `kinetic_model`, `reverse`, `id__in`; order by `id` |
| `/api/transport/` | order by `id` |
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

## One species or one reaction across models

`inchi` on `/api/species/` is an exact match, unlike `search`. A standard InChI (as in ChemKED)
also matches the records that add RMG's `/u` and `/lp` layers, so `inchi=1S/O2/c1-2` gives the
triplet and the singlet O2 records; add `multiplicity=3` for the triplet. `has_electronic_state=false`
leaves out labelled excited states such as OH*. An InChI with RMG's layers matches that record only.

```bash
curl "https://pr.omethe.us/api/species/?inchi=1S/CH3O/c1-2/h1H3&has_electronic_state=false"  # -> 33
curl "https://pr.omethe.us/api/thermo/?species=33&reference=false&page_size=1000"        # every model's entry
curl "https://pr.omethe.us/api/thermo-record/?species=33&provider=atct"                  # the ATcT value
```

A reaction written in the other direction is a second reaction record with the same
`canonical_key` (`canonical_direction` is +1 or -1). Filter by `canonical_key` to get both:

```bash
curl "https://pr.omethe.us/api/reaction/?species=5&species=9&species=10&species=6"       # H2 + OH = H2O + H
curl "https://pr.omethe.us/api/kinetics/?canonical_key=<key>&page_size=1000"             # every model's rate
curl "https://pr.omethe.us/api/kinetics/?reaction=10179&kinetic_model=125"              # one model's rate
```

`rate_fingerprint` on a rate record is log10 k in SI units (m, mol, s) at 500, 1000 and 1500 K and
1 bar, calculated from `data` as written: colliders at efficiency 1, and a duplicate entry alone
(not summed with its partner). It is empty when the rate cannot be evaluated.

## Downloads and the original mechanism

Each model page offers four downloads, at `/kineticmodel/<id>/download/<format>`:

| Format | What it is |
|--------|------------|
| `chemkin` | The Prometheus record of the model as a CHEMKIN bundle (.zip), written from the database |
| `cantera` | The same record as a Cantera YAML file |
| `chemkin-original` | The original mechanism: the model's own CHEMKIN files as they are (the files uploaded for the model, or the files RMG-models converted), with a `README.txt` that says where they come from |
| `cantera-original` | The original mechanism through Cantera's `ck2yaml`, with no change to the files. Comment lines at the top say where the files come from, and whether Cantera loads the result |

The Prometheus record can have fewer reactions than the model's own file. RMG-Py does not read a
reaction with a coefficient that is not a whole number (`NC12-QOOH=>1.2NC10H20+HO2`), RMG-models
did not identify every species, and the generated downloads leave out a reaction whose species has
no thermo. The top of each generated download says how many of the file's reaction lines it has and
gives the line numbers of the others, by reason. The model page shows the same count. For the full
list:

```bash
curl "https://pr.omethe.us/api/kineticmodel/213/coverage/"            # the lines not in the downloads
curl "https://pr.omethe.us/api/kineticmodel/213/coverage/?lines=all"  # every line
```

The response gives `file` (the model's CHEMKIN file in RMG-models, or `null`), `lines`,
`in_download`, `left_out` (lines by reason: `fractional`, `not_identified`, `not_in_prometheus`,
`no_thermo`, `falloff_same_side`) and `reaction_lines`: each line's number, text, status and the
names of its species that Prometheus does not have. A line counts as in the downloads when a
reaction of the model has its species on the two sides; colliders and rates are not compared.

Look up the literature source behind a model:

```bash
curl "https://pr.omethe.us/api/source/?search=10.1016/j.combustflame"
```
