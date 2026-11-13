# Use cases

Each use case asks one question about combustion chemistry or about the data, and answers it with
the API only. A use case page gives:

1. the question;
2. the requests that answer it, and what each response gives;
3. a Python script that you can copy and run;
4. the result that the script printed;
5. a plot of the result;
6. what the result shows.

## How the database links the data

These terms appear on every page.

- **Species record** (`/api/species/`). Each chemical species has one species record. The species
  record identifies the species by its structure, given as an InChI. Each kinetic model has its own
  name for the species, for example `CH3O` or `ch3o`. The database links each of these names to the
  same species record. The experiments use the same species records for the components of their
  mixtures.
- **Thermochemistry entry** (`/api/thermo/`). One set of NASA polynomials for one species: the heat
  capacity, enthalpy and entropy as functions of temperature. Most entries belong to kinetic models.
  When two models give identical polynomials, the database stores them as one entry, and both models
  link to it. Other entries belong to a reference record; their field `provider_record` gives that
  record. `reference=false` selects the entries of the models, and `reference=true` the entries of the
  reference records.
- **Reference record** (`/api/thermo-record/`). The thermochemistry of one species from one outside
  source. The field `provider` names the source: `atct` (Active Thermochemical Tables), `burcat`,
  `group_additivity`, `rmg_thermo_library`, or `atct_constrained` (the ATcT enthalpy with the heat
  capacity and entropy of group additivity). A reference record gives the enthalpy of formation at
  0 K and at 298.15 K with its uncertainty, the entropy at 298.15 K, the version and the provenance.
  When the source gives a full curve, the field `nasa_thermo` gives the ID of its thermochemistry
  entry. ATcT gives only enthalpies, so an ATcT record has no thermochemistry entry.
- **Reaction record** (`/api/reaction/`). Each reaction has one reaction record. The reaction record
  identifies the reaction by the species records of its reactants and products. A reaction in the
  opposite direction is a second reaction record with the same `canonical_key`.
- **Rate record** (`/api/kinetics/`). The rate parameters that a model gives for one reaction. Like a
  thermochemistry entry, a rate record is stored once, and each model that uses it links to it.

Thus a program can start from one species record or one reaction record and find the data of every
model and every experiment that use it.

## Running the scripts

Each script needs Python 3, `matplotlib` and `numpy`; the requests use only the Python standard
library. Use case 16 also needs `scipy`. Use cases 10, 17 and 18 also need [PyTeCK](https://github.com/pr-omethe-us/PyTeCK) (0.2.6),
[PyKED](https://github.com/pr-omethe-us/PyKED) (0.5.0) and [Cantera](https://cantera.org) 3.1 or
newer. The scripts import small helper files (below); put them in the same folder as the scripts.
Each script is divided into cells by lines that start with `# %%`, so VS Code, PyCharm or Jupyter
can run it one cell at a time.

```bash
pip install matplotlib numpy scipy
pip install pyteck pyked "cantera>=3.1"     # only for use cases 10, 17 and 18
python uc05_rate_one_reaction.py            # prints the result and writes uc05_rate_one_reaction.svg and .png
```

The scripts send their requests to `https://pr.omethe.us`. To use another instance, set
`PROMETHEUS_API`, for example `PROMETHEUS_API=http://127.0.0.1:8000`. The database grows, so a new
run can give larger counts than the results on these pages. `docs/use-cases/build.py` runs all the
scripts again and updates the results and the plots.

??? example "prometheus_api.py: requests and plot style"

    [Download prometheus_api.py](code/prometheus_api.py)

    ```python
    --8<-- "code/prometheus_api.py"
    ```

??? example "chem_tools.py: thermochemistry and rate coefficients"

    [Download chem_tools.py](code/chem_tools.py)

    ```python
    --8<-- "code/chem_tools.py"
    ```

??? example "pyteck_tools.py: simulate a ChemKED dataset in PyTeCK (use cases 10, 17 and 18)"

    [Download pyteck_tools.py](code/pyteck_tools.py)

    ```python
    --8<-- "code/pyteck_tools.py"
    ```
