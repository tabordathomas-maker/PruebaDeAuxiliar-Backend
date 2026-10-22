"""Modelos de entrada y salida de la API compartidos entre routers."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from biblioteca.application.users import UserProfile
from biblioteca.domain.entities import Book, Category, Loan, LoanModification, LoanStatus


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
    requested_at: datetime
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
            requested_at=loan.requested_at,
            loaned_at=loan.loaned_at,
            due_at=loan.due_at,
            returned_at=loan.returned_at,
        )


class LoanModificationResponse(BaseModel):
    id: UUID
    loan_id: UUID
    modified_by: UUID
    modified_at: datetime
    changed_fields: list[str]
    old_values: dict[str, str | None]
    new_values: dict[str, str | None]
    reason: str | None

    @classmethod
    def of(cls, modification: LoanModification) -> "LoanModificationResponse":
        return cls(
            id=modification.id,
            loan_id=modification.loan_id,
            modified_by=modification.modified_by,
            modified_at=modification.modified_at,
            changed_fields=modification.changed_fields,
            old_values=modification.old_values,
            new_values=modification.new_values,
            reason=modification.reason,
        )


class UserProfileResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    active: bool

    @classmethod
    def of(cls, profile: UserProfile) -> "UserProfileResponse":
        return cls(
            id=profile.id,
            name=profile.name,
            email=profile.email,
            role=profile.role,
            active=profile.active,
        )
