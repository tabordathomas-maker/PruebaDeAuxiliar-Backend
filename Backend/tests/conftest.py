"""Fixtures compartidos: repositorios en memoria y servicios de seguridad de prueba."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from biblioteca.adapters.http.dependencies import get_hasher, get_token_service, get_uow
from biblioteca.adapters.persistence.memory import InMemoryStore, InMemoryUnitOfWork
from biblioteca.adapters.security.jwt_tokens import JwtTokenService
from biblioteca.application.auth import RegisterUser
from biblioteca.domain.entities import Principal, RoleName, User
from biblioteca.domain.ports import PasswordHasher
from biblioteca.main import create_app


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
