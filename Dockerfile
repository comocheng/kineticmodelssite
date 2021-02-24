# Fetch RMG-Py build
FROM comocheng/kms-rmgpy:latest as rmgpy

# Application
FROM python:3.9-alpine

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  POETRY_HOME="/opt/poetry" \
  POETRY_NO_INTERACTION=1

COPY --from=rmgpy /rmg/RMG-Py/rmgpy /rmgpy

RUN apk add --no-cache curl \
  && (curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -)
ENV PATH="$POETRY_HOME/bin:$PATH" \
  PYTHONPATH="/rmgpy:$PYTHONPATH"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-interaction

COPY . .

CMD [ "./bin/entrypoint.sh" ]
