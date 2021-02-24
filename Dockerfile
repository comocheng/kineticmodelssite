# RMG build from source stage
FROM continuumio/miniconda3:latest as rmg

RUN apt update && apt -y install \
  g++ \
  gcc \
  git \
  make

WORKDIR /rmg
RUN git clone https://github.com/ReactionMechanismGenerator/RMG-Py.git \
  && git clone https://github.com/ReactionMechanismGenerator/RMG-database.git

WORKDIR /rmg/RMG-Py
ENV PYTHONUNBUFFERED=1

RUN conda env create -v --file environment.yml
SHELL ["conda", "run", "-n", "rmg_env", "/bin/bash", "-c"]
RUN make

# Application
FROM python:3.9-alpine

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  POETRY_HOME="/opt/poetry" \
  POETRY_NO_INTERACTION=1

COPY --from=rmg /rmg/RMG-Py/rmgpy /rmgpy

RUN apk add --no-cache curl \
  && (curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -)
ENV PATH="$POETRY_HOME/bin:$PATH" \
  PYTHONPATH="/rmgpy:$PYTHONPATH"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-interaction

COPY . .

CMD [ "./bin/entrypoint.sh" ]
