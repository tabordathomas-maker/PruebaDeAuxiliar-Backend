from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import BusinessRuleError, NotFoundError
from biblioteca.application.loans import ApproveLoan, BorrowBook
from biblioteca.domain.entities import LoanStatus


@pytest.fixture
def book(memory_uow):
    return CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 2)


def _available(uow, book_id) -> int:
    with uow:
        return uow.books.get(book_id).available_copies


def test_borrow_creates_pending_loan_and_reserves_a_copy(memory_uow, book, reader):
    loan = BorrowBook(memory_uow).execute(reader.user.id, book.id)

    assert loan.status is LoanStatus.PENDING
    assert loan.user_id == reader.user.id and loan.book_id == book.id
    assert loan.loaned_at is None and loan.due_at is None
    assert _available(memory_uow, book.id) == 1
    with memory_uow:
        assert memory_uow.loans.get(loan.id) == loan


def test_borrow_records_when_the_loan_was_requested(memory_uow, book, reader):
    # Arrange
    requested = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)

    # Act
    loan = BorrowBook(memory_uow, clock=lambda: requested).execute(reader.user.id, book.id)

    # Assert
    assert loan.requested_at == requested
    with memory_uow:
        assert memory_uow.loans.get(loan.id).requested_at == requested


def test_approval_keeps_the_request_date(memory_uow, book, reader):
    # Arrange
    requested = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)
    approved = requested + timedelta(days=1)
    pending = BorrowBook(memory_uow, clock=lambda: requested).execute(reader.user.id, book.id)

    # Act
    loan = ApproveLoan(memory_uow, 14, clock=lambda: approved).execute(pending.id)

    # Assert
    assert (loan.requested_at, loan.loaned_at) == (requested, approved)


def test_borrow_fails_when_no_copies_are_left(memory_uow, book, create_account):
    BorrowBook(memory_uow).execute(create_account().user.id, book.id)
    BorrowBook(memory_uow).execute(create_account().user.id, book.id)

    with pytest.raises(BusinessRuleError, match="ejemplares"):
        BorrowBook(memory_uow).execute(create_account().user.id, book.id)

    assert _available(memory_uow, book.id) == 0


def test_user_cannot_hold_two_open_loans_of_the_same_book(memory_uow, book, reader):
    BorrowBook(memory_uow).execute(reader.user.id, book.id)

    with pytest.raises(BusinessRuleError, match="abierto"):
        BorrowBook(memory_uow).execute(reader.user.id, book.id)

    assert _available(memory_uow, book.id) == 1


def test_borrow_unknown_book_fails(memory_uow, reader):
    with pytest.raises(NotFoundError):
        BorrowBook(memory_uow).execute(reader.user.id, uuid4())


def test_borrow_locks_the_book_row(mock_uow, book):
    mock_uow.books.get.return_value = book
    mock_uow.loans.list.return_value = []

    BorrowBook(mock_uow).execute(uuid4(), book.id)

    mock_uow.books.get.assert_called_once_with(book.id, for_update=True)
    mock_uow.commit.assert_called_once_with()
