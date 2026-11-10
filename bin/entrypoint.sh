#!/bin/bash

python manage.py collectstatic --noinput
python manage.py migrate --noinput
# The SQL console reads through its own read-only login. Grant it the tables of this
# migration; if the checks of the login fail, the console stays off.
if [ -n "$LIVEQUERY_DB_USER" ] && ! python manage.py livequery_role; then
    echo "The SQL console login failed its checks, so the console stays off." >&2
    unset LIVEQUERY_DB_USER LIVEQUERY_DB_PASSWORD
fi
# Build the documentation site into the shared static volume so nginx serves it
# at /docs/ (see nginx/nginx.conf). Not --strict here, so a doc warning never
# blocks startup; use bin/build-docs.sh for strict validation in dev/CI.
# DOCS_ROOT tells Django the same place, for a request that reaches it without nginx.
export DOCS_ROOT=/app/static/docs
mkdocs build -d "$DOCS_ROOT"
gunicorn kms.wsgi --bind 0.0.0.0:8000
