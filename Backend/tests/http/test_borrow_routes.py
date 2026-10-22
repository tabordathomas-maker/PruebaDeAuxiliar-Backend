from uuid import uuid4

import pytest

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


@pytest.fixture
def book_id(client, librarian) -> str:
    return client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]


def test_user_borrows_a_book_for_themselves(client, reader, book_id):
    response = client.post("/loans", json={"book_id": book_id}, headers=reader.headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["user_id"] == str(reader.user.id)


def test_borrow_without_copies_returns_409(client, create_account, book_id):
    first, second = create_account(), create_account()
    client.post("/loans", json={"book_id": book_id}, headers=first.headers)

    response = client.post("/loans", json={"book_id": book_id}, headers=second.headers)

    assert response.status_code == 409


def test_borrow_unknown_book_returns_404(client, reader):
    response = client.post("/loans", json={"book_id": str(uuid4())}, headers=reader.headers)

    assert response.status_code == 404


def test_librarian_cannot_borrow(client, librarian, book_id):
    response = client.post("/loans", json={"book_id": book_id}, headers=librarian.headers)

    assert response.status_code == 403


def test_borrow_requires_token(client, book_id):
    assert client.post("/loans", json={"book_id": book_id}).status_code == 401
