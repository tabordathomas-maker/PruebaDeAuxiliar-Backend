# Imagen de la API. Dos etapas: la primera instala las dependencias con Poetry y la
# segunda solo copia el entorno virtual, así la imagen final no lleva Poetry.
FROM python:3.14-slim AS builder

ENV POETRY_VERSION=2.5.1 \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Primero las dependencias, para que Docker reutilice esta capa si solo cambia el código.
COPY pyproject.toml poetry.lock poetry.toml README.md ./
RUN poetry install --only main --no-root

COPY src ./src
RUN poetry install --only main


FROM python:3.14-slim

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 1000 biblioteca

COPY --from=builder /app/.venv ./.venv
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

USER biblioteca

EXPOSE 8000

# Aplica las migraciones, crea las cuentas iniciales si faltan y arranca la API.
CMD ["sh", "-c", "alembic upgrade head && python -m biblioteca.seed && exec uvicorn biblioteca.main:app --host 0.0.0.0 --port 8000"]
