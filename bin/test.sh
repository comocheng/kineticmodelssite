#!/bin/bash

set -e

poetry run python -m flake8
poetry run python manage.py test --settings=kms.test_settings --pattern="test_*unit.py" --noinput
