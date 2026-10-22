from uuid import uuid4

import pytest

from biblioteca.application.catalog import (
    AssignCategories,
    CreateBook,
    CreateCategory,
    ListCategories,
)
from biblioteca.application.errors import BusinessRuleError, ConflictError, NotFoundError
from biblioteca.domain.ports import UnitOfWork


def test_create_category_trims_and_stores_it(memory_uow):
    category = CreateCategory(memory_uow).execute("  Novela ")

    assert category.name == "Novela"
    assert [c.name for c in ListCategories(memory_uow).execute()] == ["Novela"]


def test_create_category_rejects_duplicates(memory_uow):
    CreateCategory(memory_uow).execute("Novela")

    with pytest.raises(ConflictError):
        CreateCategory(memory_uow).execute("Novela")


def test_create_book_starts_with_all_copies_available(memory_uow):
    novel = CreateCategory(memory_uow).execute("Novela")

    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 3, [novel.id])

    assert book.available_copies == book.total_copies == 3
    with memory_uow:
        assert memory_uow.books.get(book.id).category_ids == {novel.id}


def test_create_book_rejects_duplicate_isbn(memory_uow):
    CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1)

    with pytest.raises(ConflictError):
        CreateBook(memory_uow).execute("Otro", "Otra", " 978-1 ", 1)


def test_create_book_requires_at_least_one_copy(mocker):
    uow = mocker.MagicMock(spec=UnitOfWork)

    with pytest.raises(BusinessRuleError):
        CreateBook(uow).execute("Rayuela", "Cortázar", "978-1", 0)

    uow.commit.assert_not_called()


def test_create_book_rejects_unknown_categories(memory_uow):
    with pytest.raises(NotFoundError):
        CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1, [uuid4()])

    with memory_uow:
        assert memory_uow.books.get_by_isbn("978-1") is None


def test_assign_categories_adds_to_existing_ones(memory_uow):
    novel = CreateCategory(memory_uow).execute("Novela")
    classic = CreateCategory(memory_uow).execute("Clásico")
    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1, [novel.id])

    updated = AssignCategories(memory_uow).execute(book.id, [classic.id, novel.id])

    assert updated.category_ids == {novel.id, classic.id}
    with memory_uow:
        assert memory_uow.books.get(book.id).category_ids == {novel.id, classic.id}


def test_assign_categories_to_unknown_book_fails(memory_uow):
    novel = CreateCategory(memory_uow).execute("Novela")

    with pytest.raises(NotFoundError):
        AssignCategories(memory_uow).execute(uuid4(), [novel.id])


def test_assign_unknown_category_fails(memory_uow):
    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1)

    with pytest.raises(NotFoundError):
        AssignCategories(memory_uow).execute(book.id, [uuid4()])
