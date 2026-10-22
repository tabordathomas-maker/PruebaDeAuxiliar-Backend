"""Auditoría de préstamos contra Postgres real: atomicidad e historial protegido (patrón AAA)."""

from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from biblioteca.adapters.persistence.postgres import tables as t
from biblioteca.application.auth import RegisterUser
from biblioteca.application.catalog import CreateBook
from biblioteca.application.loans import ApproveLoan, BorrowBook, ModifyLoanTerms
from biblioteca.domain.entities import RoleName


@pytest.fixture
def active_loan(postgres_uow, hasher):
    book = CreateBook(postgres_uow).execute("Rayuela", "Cortázar", "978-1", 1)
    reader = RegisterUser(postgres_uow, hasher).execute("Ana", "ana@example.com", "secreto123")
    pending = BorrowBook(postgres_uow).execute(reader.id, book.id)
    return ApproveLoan(postgres_uow, 14).execute(pending.id)


@pytest.fixture
def librarian(postgres_uow, hasher):
    return RegisterUser(postgres_uow, hasher).execute(
        "Luz", "luz@example.com", "secreto123", role=RoleName.LIBRARIAN
    )


def test_modification_and_audit_are_committed_together(postgres_uow, active_loan, librarian):
    # Arrange
    use_case = ModifyLoanTerms(postgres_uow)

    # Act
    loan = use_case.execute(librarian.id, active_loan.id, duration_days=30)

    # Assert
    with postgres_uow:
        assert postgres_uow.loans.get(active_loan.id).due_at == loan.due_at
        [audit] = postgres_uow.loan_modifications.list_by_loan(active_loan.id)
        assert audit.modified_by == librarian.id
        assert audit.modified_at.tzinfo is not None


def test_a_failing_audit_insert_rolls_back_the_loan_change(postgres_uow, active_loan):
    # Arrange: el autor no existe, así que la llave foránea de la auditoría falla en la base.
    ghost_actor = uuid4()

    # Act
    with pytest.raises(IntegrityError):
        ModifyLoanTerms(postgres_uow).execute(ghost_actor, active_loan.id, duration_days=30)

    # Assert
    with postgres_uow:
        assert postgres_uow.loans.get(active_loan.id).due_at == active_loan.due_at
        assert postgres_uow.loan_modifications.list_by_loan(active_loan.id) == []


@pytest.mark.parametrize("table", ["users", "loans"])
def test_database_refuses_to_delete_rows_referenced_by_the_history(
    postgres_uow, active_loan, librarian, table
):
    # Arrange
    ModifyLoanTerms(postgres_uow).execute(librarian.id, active_loan.id, duration_days=30)
    target = {
        "users": delete(t.users).where(t.users.c.id == librarian.id),
        "loans": delete(t.loans).where(t.loans.c.id == active_loan.id),
    }[table]

    # Act
    with pytest.raises(IntegrityError):
        with postgres_uow:
            postgres_uow.session.execute(target)
            postgres_uow.commit()

    # Assert
    with postgres_uow:
        assert len(postgres_uow.loan_modifications.list_by_loan(active_loan.id)) == 1
