from fastapi.testclient import TestClient

from biblioteca.main import create_app


def test_base_route_returns_200():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
