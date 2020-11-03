#!/bin/bash

python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn kms.wsgi --bind 0.0.0.0:8000
