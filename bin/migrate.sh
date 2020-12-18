#!/bin/bash

pip install debugpy -t /tmp
python /tmp/debugpy --wait-for-client --listen 0.0.0.0:5678 manage.py migrate
