#!/bin/bash

python -m flake8
python manage.py test --settings=kms.test_settings --noinput
