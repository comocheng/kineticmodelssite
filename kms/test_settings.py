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
