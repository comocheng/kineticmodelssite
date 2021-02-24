#!/bin/bash
poetry run python manage.py migrate --noinput
poetry run gunicorn kms.wsgi --bind 0.0.0.0:8000
