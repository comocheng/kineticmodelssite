# Local Setup Guide (Without Docker)

This guide walks you through setting up and running the **kineticmodelssite** Django project directly on your machine — no Docker required.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | 3.9 | Required (RMG compatibility) |
| **PostgreSQL** | 12+ | [Postgres.app](https://postgresapp.com/) recommended on macOS |
| **Conda** | Any | [Miniforge](https://github.com/conda-forge/miniforge) recommended |
| **Git** | Any | For cloning RMG-models |

---

## 1. Clone the Repository

```bash
git clone https://github.com/LekiaAnonim/kineticmodelssite.git
cd kineticmodelssite
```

---

## 2. Create the Conda Environment

```bash
conda env create -f environment.yml
conda activate kms
```

> **Apple Silicon (M1/M2/M3) note:** RMG 3.3.0 is only available for `linux-64`. You can still install the rest of the environment and comment out the `rmg=3.3.0` line in `environment.yml` if RMG is not needed for your workflow. Alternatively, install RMG separately from source ([RMG-Py](https://github.com/ReactionMechanismGenerator/RMG-Py)).

---

## 3. Set Up PostgreSQL

### Install PostgreSQL (if not already installed)

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**macOS (Postgres.app):**  
Download from [postgresapp.com](https://postgresapp.com/) and launch.

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Create the Database

```bash
createdb kms
```

Or via `psql`:
```bash
psql -U postgres -c "CREATE DATABASE kms;"
```

---

## 4. Configure Environment Variables

The project uses a `.env.dev` file for configuration. Create or edit it in the project root:

```bash
cp .env.dev .env.dev  # or create a new one
```

Edit `.env.dev` with your local paths:

```bash
# RMG-Py path (if installed)
RMGpy=/path/to/RMG-Py
PYTHONPATH=${RMGpy}:${PYTHONPATH}

# PostgreSQL settings
POSTGRES_DB=kms
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DB_HOST=localhost
DATABASE_URL=postgresql://localhost/kms

# Django settings
DJANGO_SECRET_KEY="your-secret-key-here"
DEBUG=True
ALLOWED_HOSTS=*

# RMG-models path (for importing kinetic models)
RMGMODELSPATH=/path/to/RMG-models

# ChemKED-database clone (for sync_chemked and the chemked-ingest workflow).
# Default: ../ChemKED-database next to this project.
CHEMKED_DATABASE_PATH=/path/to/ChemKED-database
```

---

## 5. Clone RMG-models (for Data Import)

If you plan to import kinetic models into the database:

```bash
git clone https://github.com/comocheng/RMG-models.git /path/to/RMG-models
```

Update `RMGMODELSPATH` in `.env.dev` to point to this directory.

---

## 6. Run Database Migrations

```bash
conda activate kms
python manage.py migrate
```

---

## 7. Load Pre-existing Data (Optional)

If a database fixture is available, decompress and load it to start with existing data:

```bash
gunzip -k fixtures/full_database.json.gz
python manage.py loaddata fixtures/full_database.json
```

This populates the database with kinetic models, species, reactions, and thermochemistry data so you don't need to run the full import process.

> **To create a fixture from an existing database** (for sharing with others):
> ```bash
> mkdir -p fixtures
> python manage.py dumpdata \
>     --natural-foreign \
>     --natural-primary \
>     --indent 2 \
>     --exclude sessions \
>     --exclude admin.logentry \
>     -o fixtures/full_database.json
> ```

---

## 8. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

---

## 9. Run the Development Server

```bash
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) in your browser.

- **Admin panel:** [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **REST API:** [http://localhost:8000/api/](http://localhost:8000/api/)
- **Importer Dashboard:** [http://localhost:8000/importer/](http://localhost:8000/importer/)

---

## Quick Start Summary

```bash
# 1. Clone and enter the project
git clone https://github.com/LekiaAnonim/kineticmodelssite.git
cd kineticmodelssite

# 2. Create conda environment
conda env create -f environment.yml
conda activate kms

# 3. Set up PostgreSQL
createdb kms

# 4. Edit .env.dev with your local paths

# 5. Migrate and load data
python manage.py migrate
gunzip -k fixtures/full_database.json.gz    # decompress fixture
python manage.py loaddata fixtures/full_database.json  # if available

# 6. Run
python manage.py runserver
```

---

## Importing Kinetic Models

To populate the database by importing from RMG-models:

```bash
# Make sure RMGMODELSPATH is set in .env.dev
python manage.py migrate
python reimport_kinetics.py
```

> **Note:** The import process can take a while depending on the number of models.

---

## REST API Authentication

Token authentication is required for write operations (POST, PUT, DELETE):

```bash
# Generate a token
python manage.py drf_create_token <username>

# Use -r to regenerate
python manage.py drf_create_token -r <username>
```

Include the token in your API requests:
```bash
curl -H "Authorization: Token <your-token>" http://localhost:8000/api/...
```

---

## Code Style

```bash
# Check style
python -m flake8

# Format code
black .
```

---

## Running Tests

```bash
python manage.py test
```

---

## Troubleshooting

### `psycopg2` build errors
If `psycopg2-binary` fails to install, try:
```bash
pip install psycopg2-binary --no-cache-dir
```

### `createdb: command not found`
Add PostgreSQL to your PATH. For Postgres.app on macOS:
```bash
export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"
```

### RMG import errors on Apple Silicon
RMG packages are compiled for x86_64. You may need to:
1. Use Rosetta 2: `arch -x86_64 conda create ...`
2. Or skip RMG and work with pre-loaded fixture data instead

### `django.db.utils.OperationalError: could not connect to server`
Make sure PostgreSQL is running:
```bash
# Homebrew
brew services start postgresql@15

# Postgres.app
# Just open the app

# Linux
sudo systemctl start postgresql
```

### Database already exists
```bash
dropdb kms && createdb kms
python manage.py migrate
python manage.py loaddata fixtures/full_database.json
```

---

## Temporary Public Access

The site's web pages and tools, including importer job controls and data editing,
currently work without signing in. Anonymous importer actions are logged as
`anonymous`, and jobs started anonymously have no `started_by` user.

Set `SITE_REQUIRE_LOGIN=True` in the deployment environment and restart the web
service to restore the previous login requirements. Django admin and REST API
write permissions remain separately enforced. POST actions still require CSRF tokens.

## Project Structure

```
kineticmodelssite/
├── kms/                  # Main Django project settings
├── database/             # Core app: models, views for kinetic data
├── api/                  # REST API app
├── importer_dashboard/   # Web UI for importing kinetic models
├── analysis/             # Jupyter notebooks for data analysis
├── fixtures/             # Database fixtures for quick setup
├── scripts/              # Utility scripts
├── manage.py             # Django management entry point
├── environment.yml       # Conda environment specification
├── .env.dev              # Environment variables (local config)
└── pyproject.toml        # Black formatter config
```
