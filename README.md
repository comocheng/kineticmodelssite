# kineticmodelssite
A django site for kinetic models

![build](https://github.com/comocheng/kineticmodelssite/workflows/Run%20Tests/badge.svg)


## Development Setup

### Using Docker for App and Database
Clone the project and set up [docker](https://www.docker.com/products/docker-desktop) and [docker-compose](https://docs.docker.com/compose/install/) (on desktop systems like Docker Desktop for Mac and Windows, Docker Compose is included as part of the Docker Desktop install). Be sure to launch the Docker.app (or ensure the docker daemon is running) before trying to run docker-compose commands.

For the first time, you need to run the initial migrations, which use [RMG-models](https://github.com/comocheng/RMG-models).
To do this, first clone the RMG-models repo via ssh or https (ssh shown below):

```git clone git@github.com:comocheng/RMG-models.git```

Now create a named volume and copy the files over using `docker`:

```docker volume create rmg-models```

```
docker run --rm \
--volume=/path/to/RMG-models:/source \
--volume=rmg-models:/target \
busybox cp -av "/source/." "/target/"
```

Then run:

```docker-compose up -d```

If you get an error ending `...returned a non-zero code: 137` then probably your Docker needs more RAM. On MacOS or Windows you can configure this using your Docker Dashboard app settings. In our experience 2GB is not enough but 4GB is.

If you use MS Visual Studio Code, you can use the debugger by running `docker-compose -f docker-compose.debug.yml up` and starting a debugging session using the project's configuration (`.vscode/launch.json`).

To run a lightweight, debuggable version of the app, run:

```docker-compose -f docker-compose.debug.yml up -d```

### Using Docker for Database Only
If you want to setup your development environment on your local machine without the docker container, install [pgAdmin4](https://www.pgadmin.org/).

Then clone the [RMG-models](https://github.com/comocheng/RMG-models) repository and set the `RMGMODELSPATH` environment variable to the path where you cloned it:

```export RMGMODELSPATH=/path/to/RMG-models/```

Also set `DB_HOST`:

```export DB_HOST=0.0.0.0```

Put these lines in your shell config file (ie. `.bashrc`) so you don't have to type it every time.

Now run:

```docker-compose -f docker-compose.debug.yml start db```

Then open pgAdmin and setup a connection with the following information:

* host: localhost
* port: 5432
* user: postgres
* password: postgres

Keep in mind this environment is not production ready. If you want to work in a production setting, use the application container defined in `docker-compose.yml` with a `.env` file in the project root.

## Project Structure:
- The main project is `kms/`
- The main app is `database/`

## Migrations:
When you build the docker container, it automatically applies all current migrations.
If you make changes to your code and need to migrate again, either rebuild the image (slow!)
or attach a shell to your running container and run the migrate command:

```docker-compose exec web sh```

Now in your interactive container shell:

```python manage.py migrate```

Similarly, if you want to nuke your migrations, you can run this in your interactive shell:

```python manage.py reset_db```

This is useful if RMG-models gets updated and you want to reset your database and migrate again.


## REST API:
Token authentication is required in order to make non readonly requests to the API (POST, PUT, DELETE, etc.).
To easily generate a token for development, use the following:

```python manage.py drf_create_token <username>```

Use the `-r` option to regenerate a token for the given user.

## Contributing:

### Code Style

We use [flake8](https://flake8.pycqa.org/en/latest/) for code style checks.
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


### Writing and Running Tests
This project uses the built-in `unittest` module with the [Django testing framework](https://docs.djangoproject.com/en/3.0/topics/testing/).

To run tests, run the shell scripts `test.sh` and `test-migrations.sh` in the docker container.

There are a few different test classes to use when writing tests. When writing simple unit test cases with no backend dependencies (ie. models), use `django.test.SimpleTestCase`. When writing unit tests with backend dependencies, use `django.test.TestCase`. When writing tests for a specific migration or series of migrations, use `django_test_migrations.contrib.unittest_case.MigratorTestCase`.

> **_IMPORTANT:_** All test files should be in the `/tests/` directory and should be prefixed with `test_` and subsequently snake-cased. Additionally, all unit tests should be suffixed with `unit` and all migration tests should be suffixed with `mig`. If you do not do this, the test shell scripts will not run properly and your tests with fail in CI!


### Version Control Strategy
1. Create a feature branch from `master`
2. When finished, rebase the feature branch to the tip of `master`
3. Open a PR and perform a Merge once approved
