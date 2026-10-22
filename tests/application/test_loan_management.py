from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import BusinessRuleError, NotFoundError, StockError
from biblioteca.application.loans import ApproveLoan, BorrowBook, CloseLoan, MarkLoanOverdue
from biblioteca.domain.entities import Book, Loan, LoanStatus

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
LOAN_DAYS = 14


@pytest.fixture
def book(memory_uow):
    return CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 2)


@pytest.fixture
def pending(memory_uow, book, reader) -> Loan:
    return BorrowBook(memory_uow).execute(reader.user.id, book.id)


def _approve(uow, loan_id, now=NOW) -> Loan:
    return ApproveLoan(uow, LOAN_DAYS, clock=lambda: now).execute(loan_id)


def _book(uow, book_id) -> Book:
    with uow:
        return uow.books.get(book_id)


# Aprobar


def test_approve_starts_the_loan_with_its_due_date(memory_uow, book, pending):
    loan = _approve(memory_uow, pending.id)

    assert loan.status is LoanStatus.ACTIVE
    assert loan.loaned_at == NOW
    assert loan.due_at == NOW + timedelta(days=LOAN_DAYS)
    # La copia ya estaba reservada: aprobar no vuelve a descontarla.
    assert _book(memory_uow, book.id).available_copies == 1


@pytest.mark.parametrize("status", [LoanStatus.ACTIVE, LoanStatus.REJECTED])
def test_only_pending_loans_can_be_approved(memory_uow, pending, status):
    if status is LoanStatus.ACTIVE:
        _approve(memory_uow, pending.id)
    else:
        CloseLoan(memory_uow).execute(pending.id)

    with pytest.raises(BusinessRuleError):
        _approve(memory_uow, pending.id)


def test_approve_fails_with_stock_error_when_copies_do_not_add_up(memory_uow, book, pending):
    # Alguien redujo los ejemplares por fuera: ya no hay copia para la reserva.
    with memory_uow:
        stored = memory_uow.books.get(book.id)
        stored.total_copies = stored.available_copies = 0
        memory_uow.books.update(stored)
        memory_uow.commit()

    with pytest.raises(StockError):
        _approve(memory_uow, pending.id)

    with memory_uow:
        assert memory_uow.loans.get(pending.id).status is LoanStatus.PENDING


def test_approve_fails_with_stock_error_when_book_is_gone(mock_uow, pending):
    mock_uow.loans.get.return_value = pending
    mock_uow.books.get.return_value = None

    with pytest.raises(StockError):
        _approve(mock_uow, pending.id)

    mock_uow.commit.assert_not_called()


def test_approve_unknown_loan_fails(memory_uow):
    with pytest.raises(NotFoundError):
        _approve(memory_uow, uuid4())


# Cerrar


def test_close_pending_rejects_it_and_restores_the_copy(memory_uow, book, pending):
    loan = CloseLoan(memory_uow).execute(pending.id)

    assert loan.status is LoanStatus.REJECTED
    assert loan.returned_at is None
    assert _book(memory_uow, book.id).available_copies == 2


@pytest.mark.parametrize("overdue", [False, True])
def test_close_loaned_book_registers_the_return(memory_uow, book, pending, overdue):
    _approve(memory_uow, pending.id, now=NOW - timedelta(days=30))
    if overdue:
        MarkLoanOverdue(memory_uow, clock=lambda: NOW).execute(pending.id)

    loan = CloseLoan(memory_uow, clock=lambda: NOW).execute(pending.id)

    assert loan.status is LoanStatus.RETURNED
    assert loan.returned_at == NOW
    assert _book(memory_uow, book.id).available_copies == 2


def test_closed_loans_cannot_be_closed_again(memory_uow, book, pending):
    CloseLoan(memory_uow).execute(pending.id)

    with pytest.raises(BusinessRuleError):
        CloseLoan(memory_uow).execute(pending.id)

    assert _book(memory_uow, book.id).available_copies == 2


# Marcar vencido


def test_mark_overdue_after_due_date(memory_uow, pending):
    _approve(memory_uow, pending.id, now=NOW - timedelta(days=LOAN_DAYS + 1))

    loan = MarkLoanOverdue(memory_uow, clock=lambda: NOW).execute(pending.id)

    assert loan.status is LoanStatus.OVERDUE


def test_cannot_mark_overdue_before_due_date(memory_uow, pending):
    _approve(memory_uow, pending.id, now=NOW)

    with pytest.raises(BusinessRuleError, match="fecha límite"):
        MarkLoanOverdue(memory_uow, clock=lambda: NOW + timedelta(days=1)).execute(pending.id)


@pytest.mark.parametrize("status", [LoanStatus.PENDING, LoanStatus.OVERDUE, LoanStatus.RETURNED])
def test_only_active_loans_can_be_marked_overdue(mock_uow, status):
    loan = Loan(uuid4(), uuid4(), status=status, due_at=NOW - timedelta(days=1))
    mock_uow.loans.get.return_value = loan

    with pytest.raises(BusinessRuleError):
        MarkLoanOverdue(mock_uow, clock=lambda: NOW).execute(loan.id)

    mock_uow.commit.assert_not_called()


# Ciclo completo


def test_full_lifecycle_keeps_copies_consistent(memory_uow, book, create_account):
    ana, luis = create_account(), create_account()
    first = BorrowBook(memory_uow).execute(ana.user.id, book.id)
    second = BorrowBook(memory_uow).execute(luis.user.id, book.id)
    assert _book(memory_uow, book.id).available_copies == 0

    _approve(memory_uow, first.id)
    CloseLoan(memory_uow).execute(second.id)
    assert _book(memory_uow, book.id).available_copies == 1

    CloseLoan(memory_uow).execute(first.id)
    assert _book(memory_uow, book.id).available_copies == 2
