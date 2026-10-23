"""Swagger indica en el resumen las rutas exclusivas de admin y bibliotecario."""

import pytest


@pytest.fixture
def summaries(client) -> dict[tuple[str, str], str]:
    paths = client.get("/openapi.json").json()["paths"]
    return {
        (method.upper(), path): operation["summary"]
        for path, operations in paths.items()
        for method, operation in operations.items()
    }


@pytest.mark.parametrize(
    ("method", "path", "summary"),
    [
        ("POST", "/categories", "Create Category (Librarian)"),
        ("POST", "/loans/{loan_id}/approve", "Approve Loan (Librarian)"),
        ("POST", "/users", "Create Account (Admin)"),
        ("PATCH", "/books/{book_id}", "Update Book (Admin, Librarian)"),
        ("DELETE", "/users/{user_id}", "Deactivate Account (Admin, Librarian)"),
    ],
)
def test_restricted_routes_show_their_roles(summaries, method, path, summary):
    # Arrange: el esquema OpenAPI de la app real (fixture summaries)

    # Act
    actual = summaries[(method, path)]

    # Assert
    assert actual == summary


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/categories"), ("POST", "/loans"), ("POST", "/auth/login"), ("GET", "/users/me")],
)
def test_other_routes_have_no_role_label(summaries, method, path):
    # Arrange: el esquema OpenAPI de la app real (fixture summaries)

    # Act
    actual = summaries[(method, path)]

    # Assert
    assert "(" not in actual
