#!/bin/bash

python manage.py test --pattern="test_*mig.py" --noinput --keepdb
