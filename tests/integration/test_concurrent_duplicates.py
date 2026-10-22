"""Dos peticiones simultáneas crean lo mismo: la segunda responde 409, no 500 (patrón AAA).

Cada caso de uso revisa el duplicado antes de insertar. Para que las dos peticiones
pasen esa revisión a la vez, una barrera retiene la búsqueda hasta que ambas la hicieron:
así la base es quien frena el duplicado y el adaptador debe traducirlo.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Thread

import pytest
from fastapi.testclient import TestClient

from biblioteca.adapters.http.dependencies import get_hasher, get_token_service, get_uow
from biblioteca.adapters.persistence.postgres import repositories as repos
from biblioteca.adapters.persistence.postgres.repositories import PostgresUnitOfWork
from biblioteca.application.auth import RegisterUser
from biblioteca.application.errors import ConflictError
from biblioteca.domain.entities import Category, Principal, RoleName
from biblioteca.main import create_app

CASES = [
    pytest.param(
        repos.PostgresUserRepository,
        "get_by_email",
        "/auth/register",
        {"name": "Ana", "email": "ana@example.com", "password": "secreto123"},
        id="email",
    ),
    pytest.param(
        repos.PostgresCategoryRepository,
        "get_by_name",
        "/categories",
        {"name": "Novela"},
        id="categoria",
    ),
    pytest.param(
        repos.PostgresBookRepository,
        "get_by_isbn",
        "/books",
        {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1},
        id="isbn",
    ),
]


@pytest.fixture
def postgres_client(postgres_uow, hasher, token_service):
    """La app real sobre Postgres; devuelve un constructor de clientes y la cabecera."""
    factory = postgres_uow.session_factory
    app = create_app()
    app.dependency_overrides[get_uow] = lambda: PostgresUnitOfWork(factory)
    app.dependency_overrides[get_hasher] = lambda: hasher
    app.dependency_overrides[get_token_service] = lambda: token_service
    librarian = RegisterUser(postgres_uow, hasher).execute(
        "Luz", "luz@example.com", "secreto123", role=RoleName.LIBRARIAN
    )
    token = token_service.issue(Principal(user_id=librarian.id, role=RoleName.LIBRARIAN))
    return app, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(("repository", "lookup", "path", "body"), CASES)
def test_simultaneous_duplicates_answer_409(
    postgres_client, monkeypatch, repository, lookup, path, body
):
    # Arrange
    app, headers = postgres_client
    both_checked = Barrier(2, timeout=10)
    original = getattr(repository, lookup)

    def lookup_then_wait(self, value):
        found = original(self, value)
        if found is None:
            both_checked.wait()
        return found

    monkeypatch.setattr(repository, lookup, lookup_then_wait)

    def send(_):
        return TestClient(app).post(path, json=body, headers=headers).status_code

    # Act
    with ThreadPoolExecutor(2) as pool:
        statuses = sorted(pool.map(send, range(2)))

    # Assert
    assert statuses == [201, 409]


def test_unique_violation_becomes_conflict_error(postgres_uow):
    # Arrange: la primera transacción inserta y espera; la segunda queda bloqueada por
    # el índice único hasta que la primera confirma.
    first, second = (PostgresUnitOfWork(postgres_uow.session_factory) for _ in range(2))
    inserted, outcome = Event(), {}

    def insert_later():
        inserted.wait()
        try:
            with second:
                second.categories.add(Category(name="Novela"))
                second.commit()
            outcome["error"] = None
        except ConflictError as error:
            outcome["error"] = error

    thread = Thread(target=insert_later)
    thread.start()

    # Act
    with first:
        first.categories.add(Category(name="Novela"))
        inserted.set()
        first.commit()
    thread.join(timeout=10)

    # Assert
    assert str(outcome["error"]) == "Ya existe la categoría Novela"
    with postgres_uow:
        assert [c.name for c in postgres_uow.categories.list()] == ["Novela"]
