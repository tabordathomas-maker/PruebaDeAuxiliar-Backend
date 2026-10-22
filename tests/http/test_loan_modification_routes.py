"""PATCH /loans/{id} y GET /loans/{id}/modifications (patrón AAA)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


@pytest.fixture
def active_loan(client, librarian, reader) -> dict:
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    loan_id = client.post("/loans", json={"book_id": book_id}, headers=reader.headers).json()["id"]
    return client.post(f"/loans/{loan_id}/approve", headers=librarian.headers).json()


def _later(loan: dict, days: int) -> str:
    return (datetime.fromisoformat(loan["loaned_at"]) + timedelta(days=days)).isoformat()


@pytest.mark.parametrize("account", ["admin", "librarian"])
def test_admin_and_librarian_change_the_due_date_and_it_is_audited(
    client, request, active_loan, account
):
    # Arrange
    actor = request.getfixturevalue(account)
    new_due = _later(active_loan, 30)

    # Act
    response = client.patch(
        f"/loans/{active_loan['id']}",
        json={"due_at": new_due, "reason": "Renovación"},
        headers=actor.headers,
    )

    # Assert
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["due_at"]) == datetime.fromisoformat(new_due)
    [audit] = client.get(f"/loans/{active_loan['id']}/modifications", headers=actor.headers).json()
    assert audit["loan_id"] == active_loan["id"]
    assert audit["modified_by"] == str(actor.user.id)
    assert audit["changed_fields"] == ["due_at"]
    assert datetime.fromisoformat(audit["old_values"]["due_at"]) == datetime.fromisoformat(
        active_loan["due_at"]
    )
    assert datetime.fromisoformat(audit["new_values"]["due_at"]) == datetime.fromisoformat(new_due)
    assert audit["reason"] == "Renovación"
    assert datetime.fromisoformat(audit["modified_at"]).tzinfo is not None


def test_duration_sets_the_due_date_from_the_start(client, librarian, active_loan):
    # Arrange
    body = {"duration_days": 21}

    # Act
    response = client.patch(f"/loans/{active_loan['id']}", json=body, headers=librarian.headers)

    # Assert
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["due_at"]) == datetime.fromisoformat(
        _later(active_loan, 21)
    )


def test_successive_changes_keep_every_record(client, librarian, admin, active_loan):
    # Arrange
    path = f"/loans/{active_loan['id']}"
    client.patch(path, json={"duration_days": 20}, headers=librarian.headers)

    # Act
    client.patch(path, json={"duration_days": 25}, headers=admin.headers)

    # Assert
    history = client.get(f"{path}/modifications", headers=librarian.headers).json()
    assert [h["modified_by"] for h in history] == [str(librarian.user.id), str(admin.user.id)]
    assert history[0]["new_values"] == history[1]["old_values"]


def test_reader_cannot_modify_loans_or_read_their_history(client, reader, active_loan):
    # Arrange
    path = f"/loans/{active_loan['id']}"

    # Act
    modify = client.patch(path, json={"duration_days": 60}, headers=reader.headers)
    history = client.get(f"{path}/modifications", headers=reader.headers)

    # Assert
    assert modify.status_code == 403
    assert history.status_code == 403
    loans = client.get("/loans/me", headers=reader.headers).json()
    assert loans[0]["due_at"] == active_loan["due_at"]


def test_requests_without_token_are_rejected(client, active_loan):
    # Arrange
    path = f"/loans/{active_loan['id']}"

    # Act
    modify = client.patch(path, json={"duration_days": 60})
    history = client.get(f"{path}/modifications")

    # Assert
    assert (modify.status_code, history.status_code) == (401, 401)


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_audit_records_cannot_be_written_through_the_api(client, librarian, active_loan, method):
    # Arrange
    path = f"/loans/{active_loan['id']}/modifications"

    # Act
    response = client.request(method, path, json={}, headers=librarian.headers)

    # Assert
    assert response.status_code == 405


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"due_at": "2026-12-01T12:00:00"},
        {"due_at": "no-es-fecha"},
        {"duration_days": 0},
        {"duration_days": 10, "due_at": "2026-12-01T12:00:00+00:00"},
        {"duration_days": 10, "status": "returned"},
    ],
    ids=["vacio", "sin-zona-horaria", "fecha-invalida", "duracion-cero", "ambos", "campo-extra"],
)
def test_invalid_requests_return_422(client, librarian, active_loan, body):
    # Arrange
    path = f"/loans/{active_loan['id']}"

    # Act
    response = client.patch(path, json=body, headers=librarian.headers)

    # Assert
    assert response.status_code == 422


def test_due_date_before_start_returns_409_without_audit(client, librarian, active_loan):
    # Arrange
    body = {"due_at": _later(active_loan, -1)}

    # Act
    response = client.patch(f"/loans/{active_loan['id']}", json=body, headers=librarian.headers)

    # Assert
    assert response.status_code == 409
    history = client.get(f"/loans/{active_loan['id']}/modifications", headers=librarian.headers)
    assert history.json() == []


def test_pending_loan_terms_cannot_be_modified(client, librarian, create_account):
    # Arrange
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    reader = create_account()
    loan_id = client.post("/loans", json={"book_id": book_id}, headers=reader.headers).json()["id"]

    # Act
    response = client.patch(
        f"/loans/{loan_id}", json={"duration_days": 10}, headers=librarian.headers
    )

    # Assert
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [("patch", "", {"duration_days": 10}), ("get", "/modifications", None)],
)
def test_unknown_loan_returns_404(client, librarian, method, suffix, body):
    # Arrange
    path = f"/loans/{uuid4()}{suffix}"

    # Act
    response = client.request(method, path, json=body, headers=librarian.headers)

    # Assert
    assert response.status_code == 404


def test_history_survives_deactivating_the_borrower(client, admin, librarian, active_loan):
    # Arrange
    path = f"/loans/{active_loan['id']}"
    client.patch(path, json={"duration_days": 20}, headers=librarian.headers)
    client.post(f"{path}/close", headers=librarian.headers)

    # Act
    deactivation = client.delete(f"/users/{active_loan['user_id']}", headers=admin.headers)

    # Assert
    assert deactivation.status_code == 204
    history = client.get(f"{path}/modifications", headers=admin.headers).json()
    assert len(history) == 1
