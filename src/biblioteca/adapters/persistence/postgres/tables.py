"""Esquema relacional que sigue el DER (docs/DER.jpg)."""

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB

from biblioteca.domain.entities import LoanStatus

metadata = MetaData()

roles = Table(
    "roles",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
)

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
    Column("active", Boolean, nullable=False, server_default=true()),
)

categories = Table(
    "categories",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
)

books = Table(
    "books",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("title", Text, nullable=False),
    Column("author", Text, nullable=False),
    Column("isbn", Text, nullable=False, unique=True),
    Column("total_copies", Integer, nullable=False),
    Column("available_copies", Integer, nullable=False),
    CheckConstraint(
        "available_copies >= 0 AND available_copies <= total_copies",
        name="ck_books_available_copies",
    ),
)

# Tabla pivote: la pareja de llaves es la PK, así un libro no se asigna dos veces
# a la misma categoría.
book_categories = Table(
    "book_categories",
    metadata,
    Column("book_id", Uuid, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id", Uuid, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    ),
)

loans = Table(
    "loans",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "user_id", Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    Column(
        "book_id", Uuid, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    Column("loaned_at", DateTime(timezone=True)),
    Column("due_at", DateTime(timezone=True)),
    Column("returned_at", DateTime(timezone=True)),
    Column(
        "status",
        Enum(LoanStatus, name="loan_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    ),
)

# Auditoría de préstamos: una fila por modificación, nunca se actualiza. RESTRICT en
# ambas llaves para que el historial no se pierda: préstamos y usuarios no se borran
# (las cuentas se desactivan).
loan_modifications = Table(
    "loan_modifications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "loan_id", Uuid, ForeignKey("loans.id", ondelete="RESTRICT"), nullable=False, index=True
    ),
    Column("modified_by", Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("modified_at", DateTime(timezone=True), nullable=False),
    Column("changed_fields", ARRAY(Text), nullable=False),
    Column("old_values", JSONB, nullable=False),
    Column("new_values", JSONB, nullable=False),
    Column("reason", Text),
)
