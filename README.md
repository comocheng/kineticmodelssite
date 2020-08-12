# kineticmodelssite
A django site for kinetic models

![build](https://github.com/comocheng/kineticmodelssite/workflows/Run%20Tests/badge.svg)


## Setup
Install Dependencies:
To get a virtual environment up and running, [install an Anaconda distribution](https://www.anaconda.com/products/individual), then run:

```conda env create -f environment.yml```

Then set up PostgreSQL:
- ```$ conda install postgresql psycopg2```
- ```$ initdb -D postgres```
- ```$ pg_ctl -D postgres -l postgres.log start```
- ```$ createuser --interactive --pwprompt``` then add user `postgres` password `postgres` as superuser (y).
- ```$ psql postgres``` then `\du` to check the `postgres` Role is defined, then `\q` to quit.
- ```$ python manage.py migrate`


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
- set your RMGMODELSPATH enviroment variable `export RMGMODELSPATH=path/to/your/RMG-models/`
- clear everything in your database (are you sure?) `$ python manage.py reset_db`
- import the models `$ python manage.py migrate database import_rmg_models`


## Contributing:

### Dev Environment
To start contributing, clone the project and setup a conda environment.

We use [flake8] for code style checks.
It is configured in the `setup.cfg` file.
To check if your changes pass the checks, run:

```python -m flake8```

We use [black](https://github.com/psf/black) to format our codebase.
To format the codebase, `cd` to the project root and run:

```black .```

If you add a `.py` file that you don't want formatted, add it to the `tool.black` section of the `pyproject.toml`.
If you don't want to it to be checked for code style either (likely!), then also add the file pattern to the `extend-exclude` option in the `flake8` section of the `setup.cfg` file.

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
3. Open a PR and perform a Merge once approved
