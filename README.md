# kineticmodelssite
A django site for kinetic models


## Setup
Install Dependencies:
- Install pipenv: https://pipenv-es.readthedocs.io/es/stable/#install-pipenv-today
- ```pipenv install --three```

To use Anaconda instead:
- Start with the standard RMG environment, then add these packages:
- ```conda install django django-model-utils django-filter```

Or:
- Use the environment defined herein, called `kms_env`:
- ```conda env create -f environment.yml```


## Project Structure:
- The main project is `kms/`
- The main app is `database/`

Check out this project's wiki for more details
https://github.com/comocheng/kineticmodelssite/wiki/Making-a-Local-Version-of-the-Site

## Importing:
To import RMG models from the importer project
- python scripts/import_RMG_models.py path/to/your/RMG-models/

## Contributing:
To start contributing, clone the project and setup a conda environment.
Then activate the environment and `pip` install the dev requirements:

```pip install -r requirements-dev.txt```

We use [black](https://github.com/psf/black) to format our codebase.
To format the codebase, `cd` to the project root and run:

```black .```

If you add a `.py` file that you don't want formatted,
add it to the `tool.black` section of the `pyproject.toml`.
