FROM tiangolo/uvicorn-gunicorn-fastapi:latest

RUN pip install poetry

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

RUN poetry install --no-interaction --no-ansi

COPY backend /app/backend
WORKDIR /app/backend

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
