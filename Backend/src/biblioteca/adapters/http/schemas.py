"""Modelos de entrada y salida de la API compartidos entre routers."""

from uuid import UUID

from pydantic import BaseModel

from biblioteca.domain.entities import Book, Category


class CategoryResponse(BaseModel):
    id: UUID
    name: str

    @classmethod
    def of(cls, category: Category) -> "CategoryResponse":
        return cls(id=category.id, name=category.name)


class BookResponse(BaseModel):
    id: UUID
    title: str
    author: str
    isbn: str
    total_copies: int
    available_copies: int
    category_ids: list[UUID]

    @classmethod
    def of(cls, book: Book) -> "BookResponse":
        return cls(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            total_copies=book.total_copies,
            available_copies=book.available_copies,
            category_ids=sorted(book.category_ids, key=str),
        )
