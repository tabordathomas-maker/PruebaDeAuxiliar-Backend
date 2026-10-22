"""Edición de los datos de un libro (patrón AAA)."""

from uuid import uuid4

import pytest

from biblioteca.application.catalog import CreateBook, UpdateBook
from biblioteca.application.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    StockError,
)
from biblioteca.application.loans import BorrowBook


@pytest.fixture
def book(memory_uow):
    return CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 3)


def _stored(uow, book_id):
    with uow:
        return uow.books.get(book_id)


def test_updates_title_author_and_isbn(memory_uow, book):
    # Arrange
    changes = {"title": " Rayuela (2024) ", "author": "Julio Cortázar", "isbn": "978-9"}

    # Act
    updated = UpdateBook(memory_uow).execute(book.id, **changes)

    # Assert
    assert (updated.title, updated.author, updated.isbn) == (
        "Rayuela (2024)",
        "Julio Cortázar",
        "978-9",
    )
    assert _stored(memory_uow, book.id).isbn == "978-9"


def test_raising_total_copies_adds_available_copies(memory_uow, book, reader):
    # Arrange
    BorrowBook(memory_uow).execute(reader.user.id, book.id)

    # Act
    updated = UpdateBook(memory_uow).execute(book.id, total_copies=5)

    # Assert
    assert (updated.total_copies, updated.available_copies) == (5, 4)


def test_lowering_total_copies_keeps_loaned_copies_retained(memory_uow, book, reader):
    # Arrange
    BorrowBook(memory_uow).execute(reader.user.id, book.id)

    # Act
    updated = UpdateBook(memory_uow).execute(book.id, total_copies=1)

    # Assert
    assert (updated.total_copies, updated.available_copies) == (1, 0)


def test_total_copies_cannot_go_below_copies_out(memory_uow, book, create_account):
    # Arrange
    for _ in range(2):
        BorrowBook(memory_uow).execute(create_account().user.id, book.id)

    # Act
    with pytest.raises(StockError):
        UpdateBook(memory_uow).execute(book.id, total_copies=1)

    # Assert
    assert _stored(memory_uow, book.id).total_copies == 3


def test_isbn_of_another_book_is_rejected(memory_uow, book):
    # Arrange
    other = CreateBook(memory_uow).execute("Ficciones", "Borges", "978-2", 1)

    # Act
    with pytest.raises(ConflictError):
        UpdateBook(memory_uow).execute(book.id, isbn=other.isbn)

    # Assert
    assert _stored(memory_uow, book.id).isbn == "978-1"


def test_keeping_the_same_isbn_is_not_a_conflict(memory_uow, book):
    # Arrange
    same_isbn = book.isbn

    # Act
    updated = UpdateBook(memory_uow).execute(book.id, isbn=same_isbn, title="Otra")

    # Assert
    assert updated.title == "Otra"


def test_zero_copies_is_rejected(memory_uow, book):
    # Arrange
    total = 0

    # Act / Assert
    with pytest.raises(BusinessRuleError):
        UpdateBook(memory_uow).execute(book.id, total_copies=total)


def test_unknown_book_returns_not_found(memory_uow):
    # Arrange
    unknown = uuid4()

    # Act / Assert
    with pytest.raises(NotFoundError):
        UpdateBook(memory_uow).execute(unknown, title="Nada")
