"""Rutas /users: permisos por rol, baja lógica y efecto sobre el token (patrón AAA)."""

from uuid import uuid4

import pytest

from biblioteca.domain.entities import RoleName

NEW_ACCOUNT = {"name": "Nueva", "email": "nueva@example.com", "password": "secreto123"}
BOOK = {"title": "Rayuela", "author": "Cortázar", "isbn": "978-1", "total_copies": 1}


# Crear


@pytest.mark.parametrize("role", ["librarian", "user"])
def test_admin_creates_librarians_and_readers(client, admin, role):
    # Arrange
    body = {**NEW_ACCOUNT, "role": role}

    # Act
    response = client.post("/users", json=body, headers=admin.headers)

    # Assert
    assert response.status_code == 201
    assert response.json()["role"] == role
    assert response.json()["active"] is True


def test_created_librarian_can_log_in(client, admin):
    # Arrange
    client.post("/users", json={**NEW_ACCOUNT, "role": "librarian"}, headers=admin.headers)

    # Act
    response = client.post(
        "/auth/login", json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]}
    )

    # Assert
    assert response.status_code == 200


def test_admin_cannot_create_admins(client, admin):
    # Arrange
    body = {**NEW_ACCOUNT, "role": "admin"}

    # Act
    response = client.post("/users", json=body, headers=admin.headers)

    # Assert
    assert response.status_code == 422


@pytest.mark.parametrize("account", ["librarian", "reader"])
def test_only_admin_creates_accounts(client, request, account):
    # Arrange
    headers = request.getfixturevalue(account).headers

    # Act
    response = client.post("/users", json={**NEW_ACCOUNT, "role": "user"}, headers=headers)

    # Assert
    assert response.status_code == 403


def test_duplicate_email_returns_409(client, admin, reader):
    # Arrange
    body = {**NEW_ACCOUNT, "email": reader.user.email, "role": "user"}

    # Act
    response = client.post("/users", json=body, headers=admin.headers)

    # Assert
    assert response.status_code == 409


# Consultar


def test_admin_lists_and_filters_accounts(client, admin, librarian, reader):
    # Arrange
    params = {"role": "librarian"}

    # Act
    everyone = client.get("/users", headers=admin.headers)
    librarians = client.get("/users", params=params, headers=admin.headers)

    # Assert
    assert {u["id"] for u in everyone.json()} == {str(librarian.user.id), str(reader.user.id)}
    assert [u["id"] for u in librarians.json()] == [str(librarian.user.id)]


def test_admin_reads_an_account(client, admin, reader):
    # Arrange
    path = f"/users/{reader.user.id}"

    # Act
    response = client.get(path, headers=admin.headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["email"] == reader.user.email


@pytest.mark.parametrize("account", ["librarian", "reader"])
def test_non_admins_cannot_list_or_read_accounts(client, request, account, admin):
    # Arrange
    headers = request.getfixturevalue(account).headers

    # Act
    listing = client.get("/users", headers=headers)
    detail = client.get(f"/users/{admin.user.id}", headers=headers)

    # Assert
    assert listing.status_code == 403
    assert detail.status_code == 403


@pytest.mark.parametrize("account", ["admin", "librarian", "reader"])
def test_every_role_reads_its_own_account(client, request, account):
    # Arrange
    me = request.getfixturevalue(account)

    # Act
    response = client.get("/users/me", headers=me.headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == str(me.user.id)


# Modificar


@pytest.mark.parametrize("role", [RoleName.LIBRARIAN, RoleName.USER])
def test_admin_updates_librarians_and_readers(client, admin, create_account, role):
    # Arrange
    target = create_account(role)

    # Act
    response = client.put(
        f"/users/{target.user.id}", json={"name": "Renombrada"}, headers=admin.headers
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "Renombrada"


def test_admin_cannot_update_another_admin(client, admin, create_account):
    # Arrange
    other_admin = create_account(RoleName.ADMIN)

    # Act
    response = client.put(
        f"/users/{other_admin.user.id}", json={"name": "X"}, headers=admin.headers
    )

    # Assert
    assert response.status_code == 403


def test_reader_updates_own_data(client, reader):
    # Arrange
    body = {"name": "Ana María", "email": "ana.maria@example.com"}

    # Act
    response = client.put("/users/me", json=body, headers=reader.headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["email"] == "ana.maria@example.com"


def test_reader_cannot_update_another_reader_by_id(client, reader, create_account):
    # Arrange
    other = create_account()

    # Act
    response = client.put(f"/users/{other.user.id}", json={"name": "X"}, headers=reader.headers)

    # Assert
    assert response.status_code == 403
    assert client.get(f"/users/{other.user.id}", headers=reader.headers).status_code == 403


@pytest.mark.parametrize("field", [{"role": "admin"}, {"active": False}, {"id": str(uuid4())}])
def test_reader_cannot_change_role_state_or_id(client, reader, field):
    # Arrange
    body = {"name": "Ana", **field}

    # Act
    response = client.put("/users/me", json=body, headers=reader.headers)

    # Assert
    assert response.status_code == 422
    assert client.get("/users/me", headers=reader.headers).json()["role"] == "user"


@pytest.mark.parametrize("account", ["admin", "librarian"])
def test_staff_cannot_use_self_service_updates(client, request, account):
    # Arrange
    headers = request.getfixturevalue(account).headers

    # Act
    response = client.put("/users/me", json={"name": "X"}, headers=headers)

    # Assert
    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [{}, {"email": "no-es-un-email"}, {"password": "corta"}, {"name": ""}],
    ids=["vacio", "email-invalido", "clave-corta", "nombre-vacio"],
)
def test_invalid_updates_return_422(client, reader, body):
    # Arrange
    path = "/users/me"

    # Act
    response = client.put(path, json=body, headers=reader.headers)

    # Assert
    assert response.status_code == 422


def test_updating_unknown_account_returns_404(client, admin):
    # Arrange
    path = f"/users/{uuid4()}"

    # Act
    response = client.put(path, json={"name": "X"}, headers=admin.headers)

    # Assert
    assert response.status_code == 404


# Desactivar


@pytest.mark.parametrize("role", [RoleName.LIBRARIAN, RoleName.USER])
def test_admin_deactivates_librarians_and_readers(client, admin, create_account, role):
    # Arrange
    target = create_account(role)

    # Act
    response = client.delete(f"/users/{target.user.id}", headers=admin.headers)

    # Assert
    assert response.status_code == 204
    assert client.get(f"/users/{target.user.id}", headers=admin.headers).json()["active"] is False


def test_librarian_deactivates_a_reader(client, admin, librarian, reader):
    # Arrange
    path = f"/users/{reader.user.id}"

    # Act
    response = client.delete(path, headers=librarian.headers)

    # Assert
    assert response.status_code == 204
    assert client.get(path, headers=admin.headers).json()["active"] is False


@pytest.mark.parametrize("target_role", [RoleName.LIBRARIAN, RoleName.ADMIN])
def test_librarian_cannot_deactivate_staff(client, librarian, create_account, target_role):
    # Arrange
    target = create_account(target_role)

    # Act
    response = client.delete(f"/users/{target.user.id}", headers=librarian.headers)

    # Assert
    assert response.status_code == 403
    assert client.get("/users/me", headers=target.headers).status_code == 200


def test_reader_deactivates_own_account_and_loses_access(client, reader):
    # Arrange
    headers = reader.headers

    # Act
    response = client.delete("/users/me", headers=headers)

    # Assert
    assert response.status_code == 204
    assert client.get("/users/me", headers=headers).status_code == 401
    login = client.post("/auth/login", json={"email": reader.user.email, "password": "secreto123"})
    assert login.status_code == 401


def test_reader_cannot_deactivate_another_reader(client, reader, create_account):
    # Arrange
    other = create_account()

    # Act
    response = client.delete(f"/users/{other.user.id}", headers=reader.headers)

    # Assert
    assert response.status_code == 403
    assert client.get("/users/me", headers=other.headers).status_code == 200


def test_reader_with_open_loans_cannot_deactivate(client, librarian, reader):
    # Arrange
    book_id = client.post("/books", json=BOOK, headers=librarian.headers).json()["id"]
    client.post("/loans", json={"book_id": book_id}, headers=reader.headers)

    # Act
    response = client.delete("/users/me", headers=reader.headers)

    # Assert
    assert response.status_code == 409
    assert client.get("/users/me", headers=reader.headers).status_code == 200


def test_deactivated_librarian_token_stops_working(client, admin, librarian):
    # Arrange
    client.delete(f"/users/{librarian.user.id}", headers=admin.headers)

    # Act
    response = client.post("/categories", json={"name": "Novela"}, headers=librarian.headers)

    # Assert
    assert response.status_code == 401


# Sin autenticación


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/users"),
        ("post", "/users"),
        ("get", "/users/me"),
        ("put", "/users/me"),
        ("delete", "/users/me"),
        ("get", f"/users/{uuid4()}"),
        ("put", f"/users/{uuid4()}"),
        ("delete", f"/users/{uuid4()}"),
    ],
)
def test_user_routes_require_a_token(client, method, path):
    # Arrange
    kwargs = {"json": {"name": "X"}} if method in {"post", "put"} else {}

    # Act
    response = client.request(method, path, **kwargs)

    # Assert
    assert response.status_code == 401
