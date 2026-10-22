"""Casos de uso del catálogo (bibliotecario): crear libros y categorías y asignarlas."""

from collections.abc import Iterable
from uuid import UUID

from biblioteca.application.errors import BusinessRuleError, ConflictError, NotFoundError
from biblioteca.domain.entities import Book, Category
from biblioteca.domain.ports import UnitOfWork


def _ensure_categories_exist(uow: UnitOfWork, category_ids: set[UUID]) -> None:
    missing = [cid for cid in category_ids if uow.categories.get(cid) is None]
    if missing:
        raise NotFoundError(f"No existen las categorías: {', '.join(map(str, missing))}")


class CreateCategory:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, name: str) -> Category:
        name = name.strip()
        with self.uow:
            if self.uow.categories.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe la categoría {name}")
            category = Category(name=name)
            self.uow.categories.add(category)
            self.uow.commit()
            return category


class ListCategories:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self) -> list[Category]:
        with self.uow:
            return self.uow.categories.list()


class CreateBook:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(
        self,
        title: str,
        author: str,
        isbn: str,
        total_copies: int,
        category_ids: Iterable[UUID] = (),
    ) -> Book:
        if total_copies < 1:
            raise BusinessRuleError("Un libro debe tener al menos un ejemplar")
        isbn = isbn.strip()
        category_ids = set(category_ids)
        with self.uow:
            if self.uow.books.get_by_isbn(isbn) is not None:
                raise ConflictError(f"Ya existe un libro con el ISBN {isbn}")
            _ensure_categories_exist(self.uow, category_ids)

            # Un libro nuevo tiene todos sus ejemplares disponibles.
            book = Book(
                title=title.strip(),
                author=author.strip(),
                isbn=isbn,
                total_copies=total_copies,
                available_copies=total_copies,
                category_ids=category_ids,
            )
            self.uow.books.add(book)
            self.uow.commit()
            return book


class AssignCategories:
    """Agrega categorías a un libro; las que ya tenía se conservan."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, book_id: UUID, category_ids: Iterable[UUID]) -> Book:
        category_ids = set(category_ids)
        with self.uow:
            book = self.uow.books.get(book_id, for_update=True)
            if book is None:
                raise NotFoundError("El libro no existe")
            _ensure_categories_exist(self.uow, category_ids)

            book.category_ids |= category_ids
            self.uow.books.update(book)
            self.uow.commit()
            return book
