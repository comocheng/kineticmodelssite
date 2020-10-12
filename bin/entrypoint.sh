#!/bin/bash

python manage.py collectstatic --noinput
gunicorn kms.wsgi --bind 0.0.0.0:8000
