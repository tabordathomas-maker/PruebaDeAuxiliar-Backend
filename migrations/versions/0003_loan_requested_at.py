"""Fecha en que se pidió cada préstamo.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("loans", sa.Column("requested_at", sa.DateTime(timezone=True)))
    # La fecha real de los préstamos existentes no se guardó. Se usa la de salida si la
    # tienen; los pendientes toman la hora de la migración.
    op.execute(sa.text("UPDATE loans SET requested_at = COALESCE(loaned_at, now())"))
    op.alter_column("loans", "requested_at", nullable=False)


def downgrade() -> None:
    op.drop_column("loans", "requested_at")
