"""Rol administrador, baja lógica de usuarios y auditoría de préstamos.

Revision ID: 0002
Revises: 0001
"""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = uuid5(NAMESPACE_URL, "biblioteca:role:admin")


def upgrade() -> None:
    roles = sa.table("roles", sa.column("id", sa.Uuid), sa.column("name", sa.Text))
    op.bulk_insert(roles, [{"id": ADMIN_ROLE_ID, "name": "admin"}])

    # Las cuentas existentes quedan activas.
    op.add_column(
        "users", sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true())
    )

    op.create_table(
        "loan_modifications",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "loan_id", sa.Uuid, sa.ForeignKey("loans.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "modified_by",
            sa.Uuid,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_fields", sa.ARRAY(sa.Text), nullable=False),
        sa.Column("old_values", JSONB, nullable=False),
        sa.Column("new_values", JSONB, nullable=False),
        sa.Column("reason", sa.Text),
    )
    op.create_index("ix_loan_modifications_loan_id", "loan_modifications", ["loan_id"])


def downgrade() -> None:
    # Destructivo: borra el historial de auditoría y falla si quedan administradores.
    op.drop_table("loan_modifications")
    op.drop_column("users", "active")
    op.execute(sa.text("DELETE FROM roles WHERE name = 'admin'"))
