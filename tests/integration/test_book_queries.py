"""Consultas que el repositorio de libros envía a Postgres (patrón AAA)."""

import pytest
from sqlalchemy import event

from biblioteca.application.catalog import (
    AssignCategories,
    CreateBook,
    CreateCategory,
    UpdateBook,
)


@pytest.fixture
def statements(postgres_engine):
    """Registra cada sentencia SQL que se ejecuta mientras dura la prueba."""
    executed: list[str] = []

    def record(conn, cursor, statement, *args):
        executed.append(statement)

    event.listen(postgres_engine, "before_cursor_execute", record)
    yield executed
    event.remove(postgres_engine, "before_cursor_execute", record)


def test_search_by_category_loads_categories_in_one_query(postgres_uow, statements):
    # Arrange
    novel = CreateCategory(postgres_uow).execute("Novela")
    classic = CreateCategory(postgres_uow).execute("Clásicos")
    for i in range(5):
        CreateBook(postgres_uow).execute(
            f"Libro {i}", "Autor", f"978-{i}", 1, [novel.id, classic.id]
        )
    statements.clear()

    # Act
    with postgres_uow:
        books = postgres_uow.books.list_by_category(novel.id)

    # Assert
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(books) == 5
    assert all(book.category_ids == {novel.id, classic.id} for book in books)
    assert len(selects) == 2


def _pivot_writes(statements: list[str]) -> list[str]:
    return [
        s
        for s in statements
        if "book_categories" in s and s.lstrip().upper().startswith(("INSERT", "DELETE"))
    ]


def test_updating_copies_does_not_rewrite_categories(postgres_uow, statements):
    # Arrange
    novel = CreateCategory(postgres_uow).execute("Novela")
    book = CreateBook(postgres_uow).execute("Rayuela", "Cortázar", "978-1", 1, [novel.id])
    statements.clear()

    # Act
    UpdateBook(postgres_uow).execute(book.id, total_copies=3)

    # Assert
    assert _pivot_writes(statements) == []
    with postgres_uow:
        assert postgres_uow.books.get(book.id).category_ids == {novel.id}


def test_assigning_categories_inserts_only_the_new_ones(postgres_uow, statements):
    # Arrange
    novel = CreateCategory(postgres_uow).execute("Novela")
    classic = CreateCategory(postgres_uow).execute("Clásicos")
    book = CreateBook(postgres_uow).execute("Rayuela", "Cortázar", "978-1", 1, [novel.id])
    statements.clear()

    # Act
    AssignCategories(postgres_uow).execute(book.id, [classic.id])

    # Assert
    writes = _pivot_writes(statements)
    assert len(writes) == 1 and writes[0].lstrip().upper().startswith("INSERT")
    with postgres_uow:
        assert postgres_uow.books.get(book.id).category_ids == {novel.id, classic.id}


def test_removed_categories_are_deleted(postgres_uow):
    # Arrange
    novel = CreateCategory(postgres_uow).execute("Novela")
    classic = CreateCategory(postgres_uow).execute("Clásicos")
    book = CreateBook(postgres_uow).execute(
        "Rayuela", "Cortázar", "978-1", 1, [novel.id, classic.id]
    )

    # Act
    with postgres_uow:
        stored = postgres_uow.books.get(book.id)
        stored.category_ids = {classic.id}
        postgres_uow.books.update(stored)
        postgres_uow.commit()

    # Assert
    with postgres_uow:
        assert postgres_uow.books.get(book.id).category_ids == {classic.id}
