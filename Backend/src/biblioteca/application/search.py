"""Caso de uso del usuario: buscar libros por categoría."""

from uuid import UUID

from biblioteca.application.errors import NotFoundError
from biblioteca.domain.entities import Book
from biblioteca.domain.ports import UnitOfWork


class SearchBooksByCategory:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, category_id: UUID) -> list[Book]:
        with self.uow:
            # Una categoría inexistente es un error, no una búsqueda sin resultados.
            if self.uow.categories.get(category_id) is None:
                raise NotFoundError("La categoría no existe")
            return self.uow.books.list_by_category(category_id)
