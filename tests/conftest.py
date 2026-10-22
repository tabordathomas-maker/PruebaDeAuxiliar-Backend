"""Fixtures compartidos: repositorios en memoria y Postgres, seguridad y cuentas de prueba.

Los fixtures de Postgres usan una base aparte (TEST_DATABASE_URL) y omiten la prueba
si no hay servidor disponible: `invoke db` lo levanta.
"""

import os
from dataclasses import dataclass
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from biblioteca.adapters.http.dependencies import get_hasher, get_token_service, get_uow
from biblioteca.adapters.persistence.memory import InMemoryStore, InMemoryUnitOfWork
from biblioteca.adapters.persistence.postgres.repositories import (
    PostgresUnitOfWork,
    build_session_factory,
)
from biblioteca.adapters.security.jwt_tokens import JwtTokenService
from biblioteca.application.auth import RegisterUser
from biblioteca.domain.entities import Principal, RoleName, User
from biblioteca.domain.ports import (
    BookRepository,
    CategoryRepository,
    LoanRepository,
    PasswordHasher,
    RoleRepository,
    UnitOfWork,
    UserRepository,
)
from biblioteca.main import create_app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://biblioteca:biblioteca@localhost:15432/biblioteca_test",
)
ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
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


class PlainHasher(PasswordHasher):
    """Hasher trivial para que las pruebas no paguen el coste de bcrypt."""

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def memory_uow(store) -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(store)


@pytest.fixture
def mock_uow(mocker):
    """Unidad de trabajo simulada: cada repositorio es un mock con la interfaz de su puerto."""
    uow = mocker.MagicMock(spec=UnitOfWork)
    uow.__enter__.return_value = uow
    uow.roles = mocker.Mock(spec=RoleRepository)
    uow.users = mocker.Mock(spec=UserRepository)
    uow.categories = mocker.Mock(spec=CategoryRepository)
    uow.books = mocker.Mock(spec=BookRepository)
    uow.loans = mocker.Mock(spec=LoanRepository)
    return uow


@pytest.fixture
def hasher() -> PasswordHasher:
    return PlainHasher()


@pytest.fixture
def token_service() -> JwtTokenService:
    return JwtTokenService("secreto-de-pruebas-con-32-bytes-o-mas", expires_minutes=5)


@pytest.fixture
def app(store, hasher, token_service):
    """La app real con el repositorio en memoria inyectado en lugar de Postgres."""
    app = create_app()
    app.dependency_overrides[get_uow] = lambda: InMemoryUnitOfWork(store)
    app.dependency_overrides[get_hasher] = lambda: hasher
    app.dependency_overrides[get_token_service] = lambda: token_service
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@dataclass
class Account:
    user: User
    headers: dict[str, str]


@pytest.fixture
def create_account(store, hasher, token_service):
    """Registra un usuario en el almacén en memoria y le emite un token."""

    def create(role: RoleName = RoleName.USER) -> Account:
        email = f"{uuid4().hex[:8]}@example.com"
        user = RegisterUser(InMemoryUnitOfWork(store), hasher).execute(
            "Cuenta", email, "secreto123", role=role
        )
        token = token_service.issue(Principal(user_id=user.id, role=role))
        return Account(user, {"Authorization": f"Bearer {token}"})

    return create


@pytest.fixture
def librarian(create_account) -> Account:
    return create_account(RoleName.LIBRARIAN)


@pytest.fixture
def reader(create_account) -> Account:
    """Una cuenta con rol usuario."""
    return create_account(RoleName.USER)
