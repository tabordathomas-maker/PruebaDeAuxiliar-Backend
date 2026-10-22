from uuid import uuid4

import pytest

from biblioteca.application.catalog import CreateBook, CreateCategory
from biblioteca.application.errors import NotFoundError
from biblioteca.application.search import SearchBooksByCategory
from biblioteca.domain.entities import Category


@pytest.fixture
def catalog(memory_uow):
    novel = CreateCategory(memory_uow).execute("Novela")
    poetry = CreateCategory(memory_uow).execute("Poesía")
    create = CreateBook(memory_uow).execute
    create("Rayuela", "Cortázar", "978-1", 1, [novel.id])
    create("Bestiario", "Cortázar", "978-2", 1, [novel.id, poetry.id])
    create("Veinte poemas", "Neruda", "978-3", 1, [poetry.id])
    return {"novel": novel, "poetry": poetry, "empty": CreateCategory(memory_uow).execute("Ensayo")}


def test_search_returns_only_books_of_that_category_sorted_by_title(memory_uow, catalog):
    books = SearchBooksByCategory(memory_uow).execute(catalog["novel"].id)

    assert [b.title for b in books] == ["Bestiario", "Rayuela"]


def test_a_book_appears_in_each_of_its_categories(memory_uow, catalog):
    books = SearchBooksByCategory(memory_uow).execute(catalog["poetry"].id)

    assert [b.title for b in books] == ["Bestiario", "Veinte poemas"]


def test_existing_category_without_books_returns_empty_list(memory_uow, catalog):
    assert SearchBooksByCategory(memory_uow).execute(catalog["empty"].id) == []


def test_unknown_category_fails(memory_uow):
    with pytest.raises(NotFoundError):
        SearchBooksByCategory(memory_uow).execute(uuid4())


def test_search_asks_the_repository_for_that_category(mock_uow):
    category = Category("Novela")
    mock_uow.categories.get.return_value = category

    SearchBooksByCategory(mock_uow).execute(category.id)

    mock_uow.books.list_by_category.assert_called_once_with(category.id)
