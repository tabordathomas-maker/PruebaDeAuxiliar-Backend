from uuid import uuid4

from biblioteca.domain.entities import Book, Loan, LoanStatus


def test_entities_get_distinct_uuid_ids():
    first = Book("Rayuela", "Cortázar", "isbn-1", 1, 1)
    second = Book("Ficciones", "Borges", "isbn-2", 1, 1)

    assert first.id != second.id


def test_new_loan_starts_pending_without_dates():
    loan = Loan(user_id=uuid4(), book_id=uuid4())

    assert loan.status is LoanStatus.PENDING
    assert loan.loaned_at is None
    assert loan.due_at is None
    assert loan.returned_at is None
