from uuid import uuid4

import pytest

from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import ForbiddenError
from biblioteca.application.loans import BorrowBook, ListLoans
from biblioteca.domain.entities import LoanStatus, Principal, RoleName


@pytest.fixture
def loans(memory_uow, create_account):
    """Ana tiene un préstamo pendiente y otro activo; Luis uno pendiente."""
    ana, luis = create_account(), create_account()
    first = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 2)
    second = CreateBook(memory_uow).execute("Ficciones", "Borges", "978-2", 2)
    borrow = BorrowBook(memory_uow).execute
    ana_pending = borrow(ana.user.id, first.id)
    ana_active = borrow(ana.user.id, second.id)
    luis_pending = borrow(luis.user.id, first.id)
    with memory_uow:
        ana_active.status = LoanStatus.ACTIVE
        memory_uow.loans.update(ana_active)
        memory_uow.commit()
    return {
        "ana": Principal(ana.user.id, RoleName.USER),
        "luis": Principal(luis.user.id, RoleName.USER),
        "librarian": Principal(uuid4(), RoleName.LIBRARIAN),
        "ids": {"ana_pending": ana_pending.id, "ana_active": ana_active.id, "luis": luis_pending.id},
    }


def _ids(loans) -> set:
    return {loan.id for loan in loans}


def test_librarian_sees_every_loan(memory_uow, loans):
    result = ListLoans(memory_uow).execute(loans["librarian"])

    assert _ids(result) == set(loans["ids"].values())


def test_librarian_filters_by_status(memory_uow, loans):
    result = ListLoans(memory_uow).execute(loans["librarian"], status=LoanStatus.PENDING)

    assert _ids(result) == {loans["ids"]["ana_pending"], loans["ids"]["luis"]}


def test_librarian_filters_by_user_and_status(memory_uow, loans):
    result = ListLoans(memory_uow).execute(
        loans["librarian"], status=LoanStatus.ACTIVE, user_id=loans["ana"].user_id
    )

    assert _ids(result) == {loans["ids"]["ana_active"]}


def test_user_sees_only_their_own_loans(memory_uow, loans):
    result = ListLoans(memory_uow).execute(loans["ana"])

    assert _ids(result) == {loans["ids"]["ana_pending"], loans["ids"]["ana_active"]}


def test_user_filters_their_loans_by_status(memory_uow, loans):
    result = ListLoans(memory_uow).execute(loans["luis"], status=LoanStatus.ACTIVE)

    assert result == []


def test_user_cannot_ask_for_someone_elses_loans(mock_uow, loans):
    with pytest.raises(ForbiddenError):
        ListLoans(mock_uow).execute(loans["ana"], user_id=loans["luis"].user_id)

    mock_uow.loans.list.assert_not_called()


def test_user_scope_is_applied_in_the_query(mock_uow, loans):
    ListLoans(mock_uow).execute(loans["ana"], status=LoanStatus.PENDING)

    mock_uow.loans.list.assert_called_once_with(
        user_id=loans["ana"].user_id, statuses=[LoanStatus.PENDING]
    )
