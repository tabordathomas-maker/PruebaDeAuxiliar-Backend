"""Un texto obligatorio en blanco responde 422 y no se guarda (patrón AAA)."""

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


def test_blank_category_name_returns_422(client, librarian):
    # Act
    response = client.post("/categories", json={"name": "   "}, headers=librarian.headers)

    # Assert
    assert response.status_code == 422
    assert client.get("/categories", headers=librarian.headers).json() == []


def test_blank_book_title_returns_422(client, librarian):
    # Act
    response = client.post("/books", json={**BOOK, "title": "  "}, headers=librarian.headers)

    # Assert
    assert response.status_code == 422
    assert "título" in response.json()["detail"]


def test_blank_author_on_update_returns_422(client, librarian):
    # Arrange
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]

    # Act
    response = client.patch(f"/books/{book_id}", json={"author": " "}, headers=librarian.headers)

    # Assert
    assert response.status_code == 422


def test_blank_name_on_register_returns_422(client):
    # Act
    response = client.post(
        "/auth/register",
        json={"name": "   ", "email": "ana@example.com", "password": "secreto123"},
    )

    # Assert
    assert response.status_code == 422
