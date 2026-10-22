"""Modelos de entrada y salida de la API compartidos entre routers."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from biblioteca.domain.entities import Book, Category, Loan, LoanStatus


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


class LoanResponse(BaseModel):
    id: UUID
    user_id: UUID
    book_id: UUID
    status: LoanStatus
    loaned_at: datetime | None
    due_at: datetime | None
    returned_at: datetime | None

    @classmethod
    def of(cls, loan: Loan) -> "LoanResponse":
        return cls(
            id=loan.id,
            user_id=loan.user_id,
            book_id=loan.book_id,
            status=loan.status,
            loaned_at=loan.loaned_at,
            due_at=loan.due_at,
            returned_at=loan.returned_at,
        )
