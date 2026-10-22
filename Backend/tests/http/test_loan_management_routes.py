from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


@pytest.fixture
def loan_id(client, librarian, reader) -> str:
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    return client.post("/loans", json={"book_id": book_id}, headers=reader.headers).json()["id"]


def test_librarian_approves_a_loan(client, librarian, loan_id):
    response = client.post(f"/loans/{loan_id}/approve", headers=librarian.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    loaned_at = datetime.fromisoformat(body["loaned_at"])
    assert datetime.fromisoformat(body["due_at"]) - loaned_at == timedelta(days=14)
    assert abs(datetime.now(UTC) - loaned_at) < timedelta(minutes=1)


def test_librarian_closes_a_pending_loan(client, librarian, loan_id):
    response = client.post(f"/loans/{loan_id}/close", headers=librarian.headers)

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_marking_overdue_before_due_date_returns_409(client, librarian, loan_id):
    client.post(f"/loans/{loan_id}/approve", headers=librarian.headers)

    response = client.post(f"/loans/{loan_id}/overdue", headers=librarian.headers)

    assert response.status_code == 409


@pytest.mark.parametrize("action", ["approve", "close", "overdue"])
def test_user_role_cannot_manage_loans(client, reader, loan_id, action):
    assert client.post(f"/loans/{loan_id}/{action}", headers=reader.headers).status_code == 403


@pytest.mark.parametrize("action", ["approve", "close", "overdue"])
def test_unknown_loan_returns_404(client, librarian, action):
    response = client.post(f"/loans/{uuid4()}/{action}", headers=librarian.headers)

    assert response.status_code == 404
