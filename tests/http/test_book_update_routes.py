"""PATCH /books/{id}: administrador y bibliotecario editan libros (patrón AAA)."""

from uuid import uuid4

import pytest

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 2}


@pytest.fixture
def book_id(client, librarian) -> str:
    return client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]


@pytest.mark.parametrize("account", ["admin", "librarian"])
def test_admin_and_librarian_update_a_book(client, request, book_id, account):
    # Arrange
    headers = request.getfixturevalue(account).headers

    # Act
    response = client.patch(
        f"/books/{book_id}", json={"title": "Rayuela (2024)", "total_copies": 4}, headers=headers
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["total_copies"], body["available_copies"]) == (
        "Rayuela (2024)",
        4,
        4,
    )


def test_reader_cannot_update_a_book(client, reader, book_id):
    # Arrange
    body = {"title": "Otro"}

    # Act
    response = client.patch(f"/books/{book_id}", json=body, headers=reader.headers)

    # Assert
    assert response.status_code == 403


def test_update_without_token_returns_401(client, book_id):
    # Arrange
    body = {"title": "Otro"}

    # Act
    response = client.patch(f"/books/{book_id}", json=body)

    # Assert
    assert response.status_code == 401


def test_unknown_book_returns_404(client, librarian):
    # Arrange
    path = f"/books/{uuid4()}"

    # Act
    response = client.patch(path, json={"title": "Otro"}, headers=librarian.headers)

    # Assert
    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [{}, {"total_copies": 0}, {"title": ""}, {"available_copies": 9}],
    ids=["vacio", "cero-copias", "titulo-vacio", "campo-no-editable"],
)
def test_invalid_updates_return_422(client, librarian, book_id, body):
    # Arrange
    path = f"/books/{book_id}"

    # Act
    response = client.patch(path, json=body, headers=librarian.headers)

    # Assert
    assert response.status_code == 422


def test_total_below_copies_out_returns_409(client, librarian, create_account, book_id):
    # Arrange
    for _ in range(2):
        client.post("/loans", json={"book_id": book_id}, headers=create_account().headers)

    # Act
    response = client.patch(
        f"/books/{book_id}", json={"total_copies": 1}, headers=librarian.headers
    )

    # Assert
    assert response.status_code == 409


def test_duplicate_isbn_returns_409(client, librarian, book_id):
    # Arrange
    client.post("/books", json={**BOOK, "isbn": "978-2"}, headers=librarian.headers)

    # Act
    response = client.patch(f"/books/{book_id}", json={"isbn": "978-2"}, headers=librarian.headers)

    # Assert
    assert response.status_code == 409
