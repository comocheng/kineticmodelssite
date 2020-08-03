# kineticmodelssite
A django site for kinetic models

![build](https://github.com/comocheng/kineticmodelssite/workflows/Run%20Tests/badge.svg)


## Setup
Install Dependencies:
To get a virtual environment up and running, [install an Anaconda distribution](https://www.anaconda.com/products/individual), then run:

```conda env create -f environment.yml```

## Quickstart:
To get a local version of the site up and running, run these commands in order:
- ```conda activate kms_env```
- ```python manage.py migrate```
- ```python manage.py runserver```

The terminal will then output which address and port the site is hosted on.

## Project Structure:
- The main project is `kms/`
- The main app is `database/`

Check out this project's wiki for more details
https://github.com/comocheng/kineticmodelssite/wiki/Making-a-Local-Version-of-the-Site

## Importing:
To import RMG models from the importer project
- python scripts/import_RMG_models.py path/to/your/RMG-models/

## Contributing:

### Dev Environment
To start contributing, clone the project and setup a conda environment.

We use [black](https://github.com/psf/black) to format our codebase.
To format the codebase, `cd` to the project root and run:

```black .```

If you add a `.py` file that you don't want formatted,
add it to the `tool.black` section of the `pyproject.toml`.

### Updating the Models
Whenever you make a change to the models, make sure to add a database migration file to reflect those changes in the database.
You can do this easily using the command:

```python manage.py makemigrations```

If you have a local database and want to update it with new migrations, run this:

```python manage.py migrate```

In order to update the models and migrate existing data to reflect the new schema, you will have to manually write a [data migration](https://docs.djangoproject.com/en/3.0/topics/migrations/#data-migrations).

### Version Control Strategy
1. Create a feature branch from `master`
2. When finished, rebase the feature branch to the tip of `master`
3. Open a PR and perform a Squash & Merge once approved
