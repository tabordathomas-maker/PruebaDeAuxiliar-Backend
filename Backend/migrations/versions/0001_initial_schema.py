"""Esquema inicial según el DER y roles base.

Revision ID: 0001
Revises:
"""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

loan_status = sa.Enum(
    "pending", "active", "overdue", "returned", "rejected", name="loan_status"
)


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "role_id", sa.Uuid, sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
        ),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.Text, nullable=False),
        sa.Column("isbn", sa.Text, nullable=False, unique=True),
        sa.Column("total_copies", sa.Integer, nullable=False),
        sa.Column("available_copies", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "available_copies >= 0 AND available_copies <= total_copies",
            name="ck_books_available_copies",
        ),
    )
    op.create_table(
        "book_categories",
        sa.Column(
            "book_id", sa.Uuid, sa.ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "category_id",
            sa.Uuid,
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "loans",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "book_id", sa.Uuid, sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("loaned_at", sa.DateTime(timezone=True)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("status", loan_status, nullable=False),
    )
    op.create_index("ix_loans_user_id", "loans", ["user_id"])
    op.create_index("ix_loans_book_id", "loans", ["book_id"])

    op.bulk_insert(
        roles,
        [
            {"id": uuid5(NAMESPACE_URL, "biblioteca:role:librarian"), "name": "librarian"},
            {"id": uuid5(NAMESPACE_URL, "biblioteca:role:user"), "name": "user"},
        ],
    )


def downgrade() -> None:
    op.drop_table("loans")
    loan_status.drop(op.get_bind(), checkfirst=True)
    op.drop_table("book_categories")
    op.drop_table("books")
    op.drop_table("categories")
    op.drop_table("users")
    op.drop_table("roles")
