from .settings import *


# Build the current schema for all apps together. Disabling only database's
# migrations breaks dependent migrations; partially syncing also creates foreign
# keys before auth_user exists. Migration tests use the normal settings instead.
MIGRATION_MODULES = {
    app.split(".apps.")[0].rsplit(".", 1)[-1]: None for app in INSTALLED_APPS
}

# The SQL console tests run through the test database. The restriction of the real login is
# a PostgreSQL role, which manage.py livequery_role creates and checks outside the tests.
DATABASES["livequery"] = {**DATABASES["default"], "TEST": {"MIRROR": "default"}}

# Tests that need drafts (git worktrees of RMG-models) turn them on with their own temporary
# repositories; the others must not touch the developer's RMG-models clone.
IMPORTER_WORKSPACES = False

# A fast-forward of the read copy in a test must not queue a reload of the models on Celery
# (importer_dashboard/model_reload.py); the tests of the reload run it directly.
RMG_MODELS_AUTO_RELOAD = False
