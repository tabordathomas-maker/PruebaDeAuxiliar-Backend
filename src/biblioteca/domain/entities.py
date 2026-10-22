"""Entidades del dominio.

Son estructuras de datos sin comportamiento: la lógica de negocio vive solo en
los casos de uso (capa application). Los identificadores son UUID generados en
el dominio para que cualquier repositorio, relacional o en memoria, los trate igual.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class RoleName(StrEnum):
    LIBRARIAN = "librarian"
    USER = "user"


class LoanStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    OVERDUE = "overdue"
    RETURNED = "returned"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Principal:
    """Quién hace la petición, tal como lo acredita el token."""

    user_id: UUID
    role: str


@dataclass
class Role:
    name: str
    id: UUID = field(default_factory=uuid4)


@dataclass
class User:
    name: str
    email: str
    password_hash: str
    role_id: UUID
    id: UUID = field(default_factory=uuid4)


@dataclass
class Category:
    name: str
    id: UUID = field(default_factory=uuid4)


@dataclass
class Book:
    title: str
    author: str
    isbn: str
    total_copies: int
    available_copies: int
    category_ids: set[UUID] = field(default_factory=set)
    id: UUID = field(default_factory=uuid4)


@dataclass
class Loan:
    user_id: UUID
    book_id: UUID
    status: LoanStatus = LoanStatus.PENDING
    loaned_at: datetime | None = None
    due_at: datetime | None = None
    returned_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
