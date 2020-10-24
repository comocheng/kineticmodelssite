# kineticmodelssite
A django site for kinetic models

![build](https://github.com/comocheng/kineticmodelssite/workflows/Run%20Tests/badge.svg)


## Development Setup
Clone the project and set up [docker](https://www.docker.com/products/docker-desktop) and [docker-compose](https://docs.docker.com/compose/install/) (on desktop systems like Docker Desktop for Mac and Windows, Docker Compose is included as part of the Docker Desktop install).

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

```docker-compose up```

If you get an error ending `...returned a non-zero code: 137` then probably your Docker needs more RAM. On MacOS or Windows you can configure this using your Docker Dashboard app settings. In our experience 2GB is not enough but 4GB is.

If you use MS Visual Studio Code, you can use the debugger by running `docker-compose -f docker-compose.debug.yml up` and starting a debugging session using the project's configuration (`.vscode/launch.json`).

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

### Version Control Strategy
1. Create a feature branch from `master`
2. When finished, rebase the feature branch to the tip of `master`
3. Open a PR and perform a Merge once approved
