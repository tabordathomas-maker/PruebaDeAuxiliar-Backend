from uuid import UUID

import pytest

from biblioteca.adapters.persistence.memory import InMemoryUnitOfWork
from biblioteca.domain.entities import LoanStatus

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


@pytest.fixture
def active_loan_id(client, store, librarian, reader) -> str:
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    loan_id = client.post("/loans", json={"book_id": book_id}, headers=reader.headers).json()["id"]
    # La aprobación es de otro caso de uso; aquí se deja el préstamo activo directamente.
    uow = InMemoryUnitOfWork(store)
    with uow:
        loan = uow.loans.get(UUID(loan_id))
        loan.status = LoanStatus.ACTIVE
        uow.loans.update(loan)
        uow.commit()
    return loan_id


def test_user_returns_their_book(client, reader, active_loan_id):
    response = client.post(f"/loans/{active_loan_id}/return", headers=reader.headers)

    assert response.status_code == 200
    assert response.json()["status"] == "returned"
    assert response.json()["returned_at"] is not None


def test_returning_twice_returns_409(client, reader, active_loan_id):
    client.post(f"/loans/{active_loan_id}/return", headers=reader.headers)

    response = client.post(f"/loans/{active_loan_id}/return", headers=reader.headers)

    assert response.status_code == 409


def test_other_user_gets_404(client, create_account, active_loan_id):
    response = client.post(f"/loans/{active_loan_id}/return", headers=create_account().headers)

    assert response.status_code == 404


def test_librarian_uses_loan_management_instead(client, librarian, active_loan_id):
    response = client.post(f"/loans/{active_loan_id}/return", headers=librarian.headers)

    assert response.status_code == 403
