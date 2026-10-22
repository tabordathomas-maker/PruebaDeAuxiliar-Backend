import pytest

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 5}


@pytest.fixture
def two_readers(client, librarian, create_account):
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    ana, luis = create_account(), create_account()
    for account in (ana, luis):
        client.post("/loans", json={"book_id": book_id}, headers=account.headers)
    return ana, luis


def test_librarian_lists_all_loans(client, librarian, two_readers):
    response = client.get("/loans", headers=librarian.headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_librarian_filters_by_user_and_status(client, librarian, two_readers):
    ana, _ = two_readers

    by_user = client.get("/loans", params={"user_id": str(ana.user.id)}, headers=librarian.headers)
    by_status = client.get("/loans", params={"status": "active"}, headers=librarian.headers)

    assert [l["user_id"] for l in by_user.json()] == [str(ana.user.id)]
    assert by_status.json() == []


def test_invalid_status_filter_returns_422(client, librarian):
    response = client.get("/loans", params={"status": "perdido"}, headers=librarian.headers)

    assert response.status_code == 422


def test_user_sees_only_their_loans(client, two_readers):
    ana, _ = two_readers

    response = client.get("/loans/me", headers=ana.headers)

    assert response.status_code == 200
    assert [l["user_id"] for l in response.json()] == [str(ana.user.id)]


def test_user_cannot_list_all_loans(client, two_readers):
    ana, _ = two_readers

    assert client.get("/loans", headers=ana.headers).status_code == 403
