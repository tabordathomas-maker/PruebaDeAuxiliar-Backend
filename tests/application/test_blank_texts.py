"""Los textos obligatorios que quedan vacíos tras quitar los espacios se rechazan (patrón AAA)."""

import pytest

from biblioteca.application.auth import RegisterUser
from biblioteca.application.catalog import CreateBook, CreateCategory, UpdateBook
from biblioteca.application.errors import InvalidInputError
from biblioteca.application.users import UpdateAccount
from biblioteca.domain.entities import Principal, RoleName

BLANKS = ["", "   ", "\t\n"]
BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


@pytest.mark.parametrize("blank", BLANKS)
def test_blank_category_name_is_rejected(memory_uow, blank):
    # Act / Assert
    with pytest.raises(InvalidInputError, match="nombre de la categoría"):
        CreateCategory(memory_uow).execute(blank)

    with memory_uow:
        assert memory_uow.categories.list() == []


@pytest.mark.parametrize("field", ["title", "author", "isbn"])
@pytest.mark.parametrize("blank", BLANKS)
def test_blank_book_text_is_rejected_on_create(mock_uow, field, blank):
    # Arrange
    data = {**BOOK, field: blank}

    # Act / Assert
    with pytest.raises(InvalidInputError):
        CreateBook(mock_uow).execute(**data)

    mock_uow.books.add.assert_not_called()
    mock_uow.commit.assert_not_called()


@pytest.mark.parametrize("field", ["title", "author", "isbn"])
def test_blank_book_text_is_rejected_on_update(memory_uow, field):
    # Arrange
    book = CreateBook(memory_uow).execute(**BOOK)

    # Act / Assert
    with pytest.raises(InvalidInputError):
        UpdateBook(memory_uow).execute(book.id, **{field: "   "})

    with memory_uow:
        stored = memory_uow.books.get(book.id)
        assert (stored.title, stored.author, stored.isbn) == ("Rayuela", "Cortázar", "978-1")


def test_texts_are_stored_trimmed(memory_uow):
    # Act
    book = CreateBook(memory_uow).execute("  Rayuela ", " Cortázar ", " 978-1 ", 1)

    # Assert
    assert (book.title, book.author, book.isbn) == ("Rayuela", "Cortázar", "978-1")


def test_blank_user_name_is_rejected_on_register(memory_uow, hasher):
    # Act / Assert
    with pytest.raises(InvalidInputError, match="nombre"):
        RegisterUser(memory_uow, hasher).execute("   ", "ana@example.com", "secreto123")

    with memory_uow:
        assert memory_uow.users.get_by_email("ana@example.com") is None


def test_blank_user_name_is_rejected_on_update(memory_uow, hasher):
    # Arrange
    admin = RegisterUser(memory_uow, hasher).execute(
        "Admin", "admin@example.com", "secreto123", role=RoleName.ADMIN
    )
    reader = RegisterUser(memory_uow, hasher).execute("Ana", "ana@example.com", "secreto123")
    actor = Principal(user_id=admin.id, role=RoleName.ADMIN)

    # Act / Assert
    with pytest.raises(InvalidInputError):
        UpdateAccount(memory_uow, hasher).execute(actor, reader.id, name="  ")

    with memory_uow:
        assert memory_uow.users.get(reader.id).name == "Ana"
