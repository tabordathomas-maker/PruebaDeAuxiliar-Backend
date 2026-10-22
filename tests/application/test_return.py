from datetime import UTC, datetime, timedelta

import pytest

from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import BusinessRuleError, NotFoundError
from biblioteca.application.loans import BorrowBook, ReturnBook
from biblioteca.domain.entities import LoanStatus

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def book(memory_uow):
    return CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1)


@pytest.fixture
def loan_in(memory_uow, book, reader):
    """Crea un préstamo del lector y lo deja en el estado pedido."""

    def build(status: LoanStatus):
        loan = BorrowBook(memory_uow).execute(reader.user.id, book.id)
        with memory_uow:
            loan.status = status
            loan.loaned_at = NOW - timedelta(days=20)
            loan.due_at = NOW - timedelta(days=6)
            memory_uow.loans.update(loan)
            memory_uow.commit()
        return loan

    return build


def _available(uow, book_id) -> int:
    with uow:
        return uow.books.get(book_id).available_copies


@pytest.mark.parametrize("status", [LoanStatus.ACTIVE, LoanStatus.OVERDUE])
def test_return_closes_the_loan_and_restores_the_copy(memory_uow, book, reader, loan_in, status):
    loan = loan_in(status)
    assert _available(memory_uow, book.id) == 0

    returned = ReturnBook(memory_uow, clock=lambda: NOW).execute(reader.user.id, loan.id)

    assert returned.status is LoanStatus.RETURNED
    assert returned.returned_at == NOW
    assert _available(memory_uow, book.id) == 1
    with memory_uow:
        assert memory_uow.loans.get(loan.id).status is LoanStatus.RETURNED


@pytest.mark.parametrize("status", [LoanStatus.PENDING, LoanStatus.RETURNED, LoanStatus.REJECTED])
def test_only_loaned_books_can_be_returned(memory_uow, book, reader, loan_in, status):
    loan = loan_in(status)

    with pytest.raises(BusinessRuleError):
        ReturnBook(memory_uow).execute(reader.user.id, loan.id)

    assert _available(memory_uow, book.id) == 0


def test_user_cannot_return_someone_elses_loan(memory_uow, book, loan_in, create_account):
    loan = loan_in(LoanStatus.ACTIVE)

    with pytest.raises(NotFoundError):
        ReturnBook(memory_uow).execute(create_account().user.id, loan.id)

    assert _available(memory_uow, book.id) == 0


def test_return_does_not_commit_when_the_rule_fails(mock_uow, loan_in):
    loan = loan_in(LoanStatus.PENDING)
    mock_uow.loans.get.return_value = loan

    with pytest.raises(BusinessRuleError):
        ReturnBook(mock_uow).execute(loan.user_id, loan.id)

    mock_uow.commit.assert_not_called()
    mock_uow.books.update.assert_not_called()
