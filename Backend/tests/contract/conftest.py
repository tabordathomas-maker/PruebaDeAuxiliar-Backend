"""Fixtures para correr el mismo contrato contra cada implementación de repositorio.

La variante Postgres usa una base aparte (TEST_DATABASE_URL) y se omite si no hay
servidor disponible: `invoke db` lo levanta.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from biblioteca.adapters.persistence.postgres.repositories import (
    PostgresUnitOfWork,
    build_session_factory,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://biblioteca:biblioteca@localhost:15432/biblioteca_test",
)
ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
DATA_TABLES = "loans, book_categories, books, categories, users"


def _create_test_database(url) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def postgres_engine():
    url = make_url(TEST_DATABASE_URL)
    try:
        _create_test_database(url)
    except OperationalError:
        pytest.skip("Postgres no está disponible; ejecuta `invoke db`")

    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_uow(postgres_engine):
    with postgres_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {DATA_TABLES} CASCADE"))
    return PostgresUnitOfWork(build_session_factory(postgres_engine))


@pytest.fixture(params=["postgres"])
def uow(request):
    return request.getfixturevalue(f"{request.param}_uow")
