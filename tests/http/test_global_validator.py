"""El validador global sobre rutas de prueba: pública, privada y solo bibliotecario."""

from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from biblioteca.adapters.http.security import current_principal, public, roles
from biblioteca.adapters.security.jwt_tokens import JwtTokenService
from biblioteca.domain.entities import Principal, RoleName

probe = APIRouter(prefix="/probe")


@probe.get("/public")
@public
def public_route():
    return {"ok": True}


@probe.get("/private")
def private_route(principal: Principal = Depends(current_principal)):
    return {"role": principal.role, "user_id": str(principal.user_id)}


@probe.get("/librarian")
@roles(RoleName.LIBRARIAN)
def librarian_route():
    return {"ok": True}


@pytest.fixture
def probe_client(app) -> TestClient:
    app.include_router(probe)
    return TestClient(app)


@pytest.fixture
def auth_header(token_service, create_account):
    def build(role: str, service: JwtTokenService = token_service) -> dict[str, str]:
        # El validador comprueba la cuenta en la base: los roles reales usan una cuenta
        # registrada; un rol inventado no puede tenerla.
        user_id = create_account(role).user.id if role in set(RoleName) else uuid4()
        token = service.issue(Principal(user_id=user_id, role=role))
        return {"Authorization": f"Bearer {token}"}

    return build


def test_public_route_needs_no_token(probe_client):
    assert probe_client.get("/probe/public").status_code == 200


def test_missing_token_returns_401(probe_client):
    response = probe_client.get("/probe/private")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer no-es-un-jwt", "Basic dXN1YXJpbzpjbGF2ZQ==", "Bearer"],
    ids=["malformed-token", "wrong-scheme", "empty-token"],
)
def test_invalid_authorization_returns_401(probe_client, authorization):
    response = probe_client.get("/probe/private", headers={"Authorization": authorization})

    assert response.status_code == 401


def test_expired_token_returns_401(probe_client, auth_header, token_service):
    expired = JwtTokenService(token_service.secret, expires_minutes=-1)

    response = probe_client.get("/probe/private", headers=auth_header("user", expired))

    assert response.status_code == 401


def test_valid_token_reaches_private_route_with_its_principal(probe_client, auth_header):
    response = probe_client.get("/probe/private", headers=auth_header(RoleName.USER))

    assert response.status_code == 200
    assert response.json()["role"] == RoleName.USER


@pytest.mark.parametrize("role", [RoleName.USER, "rol-inventado"])
def test_wrong_role_returns_403(probe_client, auth_header, role):
    response = probe_client.get("/probe/librarian", headers=auth_header(role))

    assert response.status_code == 403


def test_librarian_role_reaches_librarian_route(probe_client, auth_header):
    response = probe_client.get("/probe/librarian", headers=auth_header(RoleName.LIBRARIAN))

    assert response.status_code == 200


def _api_routes(routes, prefix=""):
    """Rutas de la app con su ruta completa, también las de los routers incluidos.

    Desde FastAPI 0.159, `app.routes` envuelve cada router incluido en un objeto que
    guarda el router original en `original_router`; sin recorrerlo no se ve ninguna ruta.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path_format, route
        included = getattr(route, "original_router", None)
        if included is not None:
            context = getattr(route, "include_context", None)
            yield from _api_routes(included.routes, prefix + getattr(context, "prefix", ""))


def test_route_walk_finds_every_documented_route(app):
    # Arrange
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    # Act
    walked = {(method, path) for path, route in _api_routes(app.routes) for method in route.methods}

    # Assert
    assert documented and documented <= walked


def test_every_app_route_is_private_unless_marked_public(app):
    """Red de seguridad: una ruta nueva sin @public queda protegida."""
    # Arrange: un error del servidor también cuenta como ruta sin proteger.
    client = TestClient(app, raise_server_exceptions=False)
    private = [
        (path, route)
        for path, route in _api_routes(app.routes)
        if not getattr(route.endpoint, "__public__", False)
    ]

    # Act
    statuses = {
        (method, path): client.request(method, path.replace("{", "").replace("}", "")).status_code
        for path, route in private
        for method in route.methods
    }

    # Assert
    assert len(private) >= 20
    assert {key: code for key, code in statuses.items() if code != 401} == {}


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_api_docs_stay_public(client, path):
    assert client.get(path).status_code == 200
