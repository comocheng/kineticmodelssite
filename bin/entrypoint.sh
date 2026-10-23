#!/bin/bash

python manage.py collectstatic --noinput
python manage.py migrate --noinput
# Build the documentation site into the shared static volume so nginx serves it
# at /docs/ (see nginx/nginx.conf). Not --strict here, so a doc warning never
# blocks startup; use bin/build-docs.sh for strict validation in dev/CI.
mkdocs build -d /app/static/docs
gunicorn kms.wsgi --bind 0.0.0.0:8000
