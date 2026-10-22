BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 2}


def test_librarian_manages_the_catalog(client, librarian):
    category = client.post("/categories", json={"name": "Novela"}, headers=librarian.headers)
    assert category.status_code == 201
    category_id = category.json()["id"]

    book = client.post("/books", json=BOOK, headers=librarian.headers)
    assert book.status_code == 201
    assert book.json()["available_copies"] == 2

    assigned = client.post(
        f"/books/{book.json()['id']}/categories",
        json={"category_ids": [category_id]},
        headers=librarian.headers,
    )
    assert assigned.status_code == 200
    assert assigned.json()["category_ids"] == [category_id]


def test_user_role_cannot_manage_the_catalog(client, reader):
    category = client.post("/categories", json={"name": "Novela"}, headers=reader.headers)
    book = client.post("/books", json=BOOK, headers=reader.headers)

    assert category.status_code == 403
    assert book.status_code == 403


def test_any_authenticated_user_lists_categories(client, librarian, reader):
    client.post("/categories", json={"name": "Novela"}, headers=librarian.headers)

    response = client.get("/categories", headers=reader.headers)

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Novela"]


def test_catalog_errors_map_to_http_codes(client, librarian):
    client.post("/books", json=BOOK, headers=librarian.headers)

    duplicate = client.post("/books", json=BOOK, headers=librarian.headers)
    unknown_book = client.post(
        "/books/00000000-0000-0000-0000-000000000000/categories",
        json={"category_ids": ["00000000-0000-0000-0000-000000000001"]},
        headers=librarian.headers,
    )
    no_copies = client.post("/books", json={**BOOK, "total_copies": 0}, headers=librarian.headers)

    assert duplicate.status_code == 409
    assert unknown_book.status_code == 404
    assert no_copies.status_code == 422
