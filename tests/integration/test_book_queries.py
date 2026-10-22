"""Consultas que el repositorio de libros envía a Postgres (patrón AAA)."""

import pytest
from sqlalchemy import event

from biblioteca.application.catalog import CreateBook, CreateCategory


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
