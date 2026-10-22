"""Modificación de plazos de préstamos y su auditoría (patrón AAA)."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from biblioteca.adapters.persistence.memory import InMemoryLoanModificationRepository
from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import BusinessRuleError, NotFoundError
from biblioteca.application.loans import (
    ApproveLoan,
    BorrowBook,
    ListLoanModifications,
    MarkLoanOverdue,
    ModifyLoanTerms,
)
from biblioteca.domain.entities import LoanStatus

APPROVED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
LOAN_DAYS = 14


@pytest.fixture
def active_loan(memory_uow, reader):
    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 2)
    pending = BorrowBook(memory_uow).execute(reader.user.id, book.id)
    return ApproveLoan(memory_uow, LOAN_DAYS, clock=lambda: APPROVED_AT).execute(pending.id)


def _modify(uow, actor_id, loan_id, now=NOW, **changes):
    return ModifyLoanTerms(uow, clock=lambda: now).execute(actor_id, loan_id, **changes)


def _history(uow, loan_id):
    return ListLoanModifications(uow).execute(loan_id)


def test_extending_the_due_date_updates_the_loan_and_writes_an_audit(
    memory_uow, librarian, active_loan
):
    # Arrange
    new_due = APPROVED_AT + timedelta(days=21)

    # Act
    loan = _modify(
        memory_uow, librarian.user.id, active_loan.id, due_at=new_due, reason="Renovación"
    )

    # Assert
    assert loan.due_at == new_due
    [audit] = _history(memory_uow, active_loan.id)
    assert audit.loan_id == active_loan.id
    assert audit.modified_by == librarian.user.id
    assert audit.modified_at == NOW
    assert audit.changed_fields == ["due_at"]
    assert audit.old_values == {"due_at": (APPROVED_AT + timedelta(days=LOAN_DAYS)).isoformat()}
    assert audit.new_values == {"due_at": new_due.isoformat()}
    assert audit.reason == "Renovación"


def test_duration_recomputes_the_due_date_from_the_loan_start(memory_uow, admin, active_loan):
    # Arrange
    duration = 30

    # Act
    loan = _modify(memory_uow, admin.user.id, active_loan.id, duration_days=duration)

    # Assert
    assert loan.due_at == APPROVED_AT + timedelta(days=duration)
    assert _history(memory_uow, active_loan.id)[0].modified_by == admin.user.id


def test_changing_the_start_date_is_audited_with_both_values(memory_uow, librarian, active_loan):
    # Arrange
    new_start = APPROVED_AT - timedelta(days=2)

    # Act
    _modify(memory_uow, librarian.user.id, active_loan.id, loaned_at=new_start)

    # Assert
    [audit] = _history(memory_uow, active_loan.id)
    assert audit.changed_fields == ["loaned_at"]
    assert audit.old_values == {"loaned_at": APPROVED_AT.isoformat()}
    assert audit.new_values == {"loaned_at": new_start.isoformat()}


def test_dates_in_other_time_zones_are_stored_in_utc(memory_uow, librarian, active_loan):
    # Arrange
    bogota_due = datetime(2026, 11, 1, 7, 0, tzinfo=timezone(timedelta(hours=-5)))

    # Act
    loan = _modify(memory_uow, librarian.user.id, active_loan.id, due_at=bogota_due)

    # Assert
    assert loan.due_at == datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    assert loan.due_at.tzinfo == UTC
    assert _history(memory_uow, active_loan.id)[0].new_values["due_at"].endswith("+00:00")


def test_extending_an_overdue_loan_reactivates_it_and_audits_the_status(
    memory_uow, librarian, active_loan
):
    # Arrange
    after_due = APPROVED_AT + timedelta(days=LOAN_DAYS + 1)
    MarkLoanOverdue(memory_uow, clock=lambda: after_due).execute(active_loan.id)
    new_due = after_due + timedelta(days=7)

    # Act
    loan = _modify(memory_uow, librarian.user.id, active_loan.id, now=after_due, due_at=new_due)

    # Assert
    assert loan.status is LoanStatus.ACTIVE
    [audit] = _history(memory_uow, active_loan.id)
    assert audit.changed_fields == ["due_at", "status"]
    assert audit.old_values["status"] == "overdue"
    assert audit.new_values["status"] == "active"


def test_two_modifications_produce_two_independent_records(
    memory_uow, librarian, admin, active_loan
):
    # Arrange
    first_due = APPROVED_AT + timedelta(days=20)
    second_due = APPROVED_AT + timedelta(days=25)
    _modify(memory_uow, librarian.user.id, active_loan.id, due_at=first_due)

    # Act
    _modify(
        memory_uow, admin.user.id, active_loan.id, now=NOW + timedelta(hours=1), due_at=second_due
    )

    # Assert
    first, second = _history(memory_uow, active_loan.id)
    assert first.id != second.id
    assert first.new_values == {"due_at": first_due.isoformat()}
    assert first.modified_by == librarian.user.id
    assert second.old_values == {"due_at": first_due.isoformat()}
    assert second.new_values == {"due_at": second_due.isoformat()}
    assert second.modified_by == admin.user.id


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"due_at": APPROVED_AT - timedelta(days=1)},
        {"due_at": APPROVED_AT},
        {"loaned_at": NOW + timedelta(days=1)},
        {"due_at": APPROVED_AT + timedelta(days=LOAN_DAYS)},
        {"due_at": APPROVED_AT + timedelta(days=20), "duration_days": 5},
        {"duration_days": 0},
        {"due_at": datetime(2026, 12, 1, 12, 0)},
    ],
    ids=[
        "sin-cambios",
        "limite-antes-de-salida",
        "limite-igual-a-salida",
        "salida-futura",
        "mismo-valor",
        "limite-y-duracion",
        "duracion-cero",
        "fecha-sin-zona-horaria",
    ],
)
def test_invalid_changes_are_rejected_without_touching_loan_or_history(
    memory_uow, librarian, active_loan, changes
):
    # Arrange
    original_due = active_loan.due_at

    # Act
    with pytest.raises(BusinessRuleError):
        _modify(memory_uow, librarian.user.id, active_loan.id, **changes)

    # Assert
    with memory_uow:
        assert memory_uow.loans.get(active_loan.id).due_at == original_due
    assert _history(memory_uow, active_loan.id) == []


@pytest.mark.parametrize("status", [LoanStatus.PENDING, LoanStatus.RETURNED, LoanStatus.REJECTED])
def test_only_active_or_overdue_loans_can_change_terms(memory_uow, librarian, active_loan, status):
    # Arrange
    with memory_uow:
        loan = memory_uow.loans.get(active_loan.id)
        loan.status = status
        memory_uow.loans.update(loan)
        memory_uow.commit()

    # Act
    with pytest.raises(BusinessRuleError):
        _modify(memory_uow, librarian.user.id, active_loan.id, duration_days=30)

    # Assert
    assert _history(memory_uow, active_loan.id) == []


def test_unknown_loan_returns_not_found(memory_uow, librarian):
    # Arrange
    unknown = uuid4()

    # Act / Assert
    with pytest.raises(NotFoundError):
        _modify(memory_uow, librarian.user.id, unknown, duration_days=30)


def test_failed_audit_write_leaves_the_loan_unchanged(memory_uow, librarian, active_loan, mocker):
    # Arrange
    mocker.patch.object(
        InMemoryLoanModificationRepository, "add", side_effect=RuntimeError("disco lleno")
    )

    # Act
    with pytest.raises(RuntimeError):
        _modify(memory_uow, librarian.user.id, active_loan.id, duration_days=30)

    # Assert
    with memory_uow:
        assert memory_uow.loans.get(active_loan.id).due_at == active_loan.due_at


def test_loan_update_and_audit_go_in_one_commit(mock_uow, active_loan):
    # Arrange
    mock_uow.loans.get.return_value = active_loan
    actor_id = uuid4()

    # Act
    ModifyLoanTerms(mock_uow, clock=lambda: NOW).execute(actor_id, active_loan.id, duration_days=30)

    # Assert
    mock_uow.loans.update.assert_called_once()
    mock_uow.loan_modifications.add.assert_called_once()
    mock_uow.commit.assert_called_once_with()


def test_history_of_an_unknown_loan_returns_not_found(memory_uow):
    # Arrange
    unknown = uuid4()

    # Act / Assert
    with pytest.raises(NotFoundError):
        ListLoanModifications(memory_uow).execute(unknown)
