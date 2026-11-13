# Use cases

Each use case asks one question about combustion chemistry or about the data, and answers it with
the API only. A use case page gives:

1. the question;
2. the requests that answer it, and what each response gives;
3. a Python script that you can copy and run;
4. the result that the script printed;
5. a plot of the result;
6. what the result shows.

--8<-- "output/run.txt"

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

## The use cases

| | Question | Main endpoints |
|---|---|---|
| **Species and thermochemistry** | | |
| [1](uc01.md) | Which species record is each of two radicals with the same formula, and which names do the models use for it? | `species`, `kineticmodel` |
| [2](uc02.md) | Which models use an enthalpy of formation that differs from ATcT? | `thermo`, `thermo-record` |
| [3](uc03.md) | How much does the heat capacity of the allyl radical differ between the models? | `thermo`, `thermo-record` |
| [4](uc04.md) | For which species do the models disagree most on the enthalpy of formation? | `thermo`, `kineticmodel` |
| **Reactions and rate coefficients** | | |
| [5](uc05.md) | Do the models agree on the rate coefficient of H + O<sub>2</sub> = O + OH? | `reaction`, `kinetics` |
| [6](uc06.md) | Which rate expressions of CH<sub>4</sub> + OH = CH<sub>3</sub> + H<sub>2</sub>O do the models share? | `kinetics`, `kineticmodel` |
| [7](uc07.md) | How does the rate coefficient of CH<sub>3</sub> + CH<sub>3</sub> (+M) = C<sub>2</sub>H<sub>6</sub> (+M) depend on pressure? | `kinetics` |
| [8](uc08.md) | In one model, which reactions consume NH<sub>2</sub>, and which are the fastest? | `kinetics`, `reaction` |
| **Kinetic models** | | |
| [9](uc09.md) | Which models contain both NH<sub>3</sub> and H<sub>2</sub>? | `kineticmodel` |
| [10](uc10.md) | How well does a model reproduce the ignition delays of one dataset (PyTeCK)? | `chemked/dataset/<id>/export/`, `kineticmodel/<id>/download/cantera` |
| **Experiments** | | |
| [11](uc11.md) | At which temperatures and pressures did the experiments measure their data? | `experiment-datapoint` |
| [12](uc12.md) | Which shock-tube ignition delays of n-heptane does the collection hold? | `ignition-delay` |
| [13](uc13.md) | Do the laboratories agree on the burning velocity of methane-air flames? | `laminar-burning-velocity` |
| [14](uc14.md) | Which jet-stirred-reactor experiment gives the most species profiles? | `speciation-measurement`, `concentration-profile` |
| **Experiments and models together** | | |
| [15](uc15.md) | For which fuels does the database hold both experiments and models? | `experiment-dataset`, `kineticmodel` |
| **FAIR metadata** | | |
| [16](uc16.md) | How many datasets give each item of FAIR metadata? | `experiment-dataset`, `license` |
| [17](uc17.md) | Which persistent identifiers link one dataset to its paper, its authors and its licence? | `experiment-dataset/<id>/metadata/` |
| **Models against models** | | |
| [18](uc18.md) | Which models share most of their rate expressions and their thermochemistry? | `kineticmodel` |
| [19](uc19.md) | Do newer models use enthalpies of formation that are closer to ATcT? | `thermo-record`, `thermo` |
| [20](uc20.md) | For which reaction families do the models disagree most on the same reaction? | `reaction`, `kinetics` |
| [21](uc21.md) | Do the reactions that a model gives in both directions obey detailed balance? | `reaction`, `kinetics`, `thermo` |
| [22](uc22.md) | How much does the thermochemistry of the models change their reverse rates? | `reaction`, `thermo` |
| **Experiments against experiments** | | |
| [23](uc23.md) | Do the laboratories agree within the uncertainties that they report? | `laminar-burning-velocity` |
| [24](uc24.md) | Do H<sub>2</sub> ignition delays depend on the signal that defines ignition? | `ignition-delay` |
| **Models against experiments (PyTeCK)** | | |
| [25](uc25.md) | Which experiments discriminate between five hydrogen models? | `chemked/dataset/<id>/export/`, `kineticmodel/<id>/download/cantera` |
| [26](uc26.md) | Which reactions cause the difference between two hydrogen models? | `kineticmodel/<id>/download/cantera`, `kineticmodel` |

## Running the scripts

Each script needs Python 3, `matplotlib` and `numpy`; the requests use only the Python standard
library. Use cases 18 and 19 also need `scipy`. Use cases 10, 25 and 26 also need [PyTeCK](https://github.com/pr-omethe-us/PyTeCK) (0.2.6),
[PyKED](https://github.com/pr-omethe-us/PyKED) (0.5.0) and [Cantera](https://cantera.org) 3.1 or
newer. The scripts import small helper files (below); put them in the same folder as the scripts.
Each script is divided into cells by lines that start with `# %%`, so VS Code, PyCharm or Jupyter
can run it one cell at a time.

```bash
pip install matplotlib numpy scipy
pip install pyteck pyked "cantera>=3.1"     # only for use cases 10, 25 and 26
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

??? example "pyteck_tools.py: simulate a ChemKED dataset in PyTeCK (use cases 10, 25 and 26)"

    [Download pyteck_tools.py](code/pyteck_tools.py)

    ```python
    --8<-- "code/pyteck_tools.py"
    ```
