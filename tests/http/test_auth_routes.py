from biblioteca.domain.entities import RoleName

CREDENTIALS = {"email": "ana@example.com", "password": "secreto123"}


def test_register_returns_201_without_password(client):
    response = client.post("/auth/register", json={"name": "Ana", **CREDENTIALS})

    assert response.status_code == 201
    assert response.json()["email"] == "ana@example.com"
    assert "password" not in response.text


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"name": "Ana", **CREDENTIALS})

    response = client.post("/auth/register", json={"name": "Ana", **CREDENTIALS})

    assert response.status_code == 409


def test_register_validates_input(client):
    response = client.post(
        "/auth/register", json={"name": "Ana", "email": "no-email", "password": "corta"}
    )

    assert response.status_code == 422


def test_login_returns_jwt_with_user_role(client, token_service):
    client.post("/auth/register", json={"name": "Ana", **CREDENTIALS})

    response = client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert token_service.decode(body["access_token"]).role == RoleName.USER


def test_login_with_wrong_password_returns_401(client):
    client.post("/auth/register", json={"name": "Ana", **CREDENTIALS})

    response = client.post("/auth/login", json={**CREDENTIALS, "password": "incorrecta"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_with_unknown_email_returns_401(client):
    response = client.post("/auth/login", json={"email": "nadie", "password": "x"})

    assert response.status_code == 401
