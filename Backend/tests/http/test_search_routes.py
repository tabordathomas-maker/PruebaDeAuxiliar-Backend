from uuid import uuid4


def test_user_searches_books_by_category(client, librarian, reader):
    category = client.post("/categories", json={"name": "Novela"}, headers=librarian.headers)
    category_id = category.json()["id"]
    client.post(
        "/books",
        json={
            "title": "Rayuela",
            "author": "Cortázar",
            "isbn": "978-1",
            "total_copies": 1,
            "category_ids": [category_id],
        },
        headers=librarian.headers,
    )

    response = client.get("/books", params={"category_id": category_id}, headers=reader.headers)

    assert response.status_code == 200
    assert [b["title"] for b in response.json()] == ["Rayuela"]


def test_search_requires_token(client):
    assert client.get("/books", params={"category_id": str(uuid4())}).status_code == 401


def test_search_unknown_category_returns_404(client, reader):
    response = client.get("/books", params={"category_id": str(uuid4())}, headers=reader.headers)

    assert response.status_code == 404


def test_search_requires_a_valid_category_id(client, reader):
    assert client.get("/books", headers=reader.headers).status_code == 422
    assert client.get("/books?category_id=abc", headers=reader.headers).status_code == 422
