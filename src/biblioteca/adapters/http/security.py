"""Validador global de rutas.

Se registra una sola vez en la app (ver main.create_app) y corre antes de cada ruta.
Toda ruta es privada por defecto y exige un JWT válido: si falta o no es válido
responde 401. También responde 401 si la cuenta del token ya no existe, está
desactivada o cambió de rol. Las rutas marcadas con @public no lo exigen. Las marcadas con
@roles(...) exigen además uno de esos roles: si el rol no corresponde responde 403.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from biblioteca.adapters.http.dependencies import get_token_service, get_uow
from biblioteca.application.auth import VerifyPrincipal
from biblioteca.domain.entities import Principal, RoleName
from biblioteca.domain.ports import TokenService, UnitOfWork

_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}
# Roles que se anuncian en el resumen de Swagger, en este orden.
_LABELED_ROLES = {RoleName.ADMIN: "Admin", RoleName.LIBRARIAN: "Librarian"}


def public(endpoint: Callable) -> Callable:
    endpoint.__public__ = True
    return endpoint


def roles(*allowed: RoleName) -> Callable[[Callable], Callable]:
    def mark(endpoint: Callable) -> Callable:
        endpoint.__roles__ = frozenset(allowed)
        return endpoint

    return mark


def global_validator(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tokens: TokenService = Depends(get_token_service),
    uow: UnitOfWork = Depends(get_uow),
) -> None:
    endpoint = request.scope.get("endpoint")
    if getattr(endpoint, "__public__", False):
        return

    if credentials is None:
        raise HTTPException(401, "Falta el token de acceso", headers=_UNAUTHORIZED_HEADERS)
    # Un token inválido o expirado lanza InvalidTokenError, que se responde con 401.
    principal = tokens.decode(credentials.credentials)

    allowed = getattr(endpoint, "__roles__", None)
    if allowed is not None and principal.role not in allowed:
        raise HTTPException(403, "Tu rol no tiene acceso a este recurso")
    # La cuenta debe seguir activa y con el rol del token (si no, InvalidTokenError: 401).
    VerifyPrincipal(uow).execute(principal)

    request.state.principal = principal


def current_principal(request: Request) -> Principal:
    """El usuario autenticado de la petición, ya validado por global_validator."""
    return request.state.principal


def label_restricted_routes(router: APIRouter) -> APIRouter:
    """Añade al resumen de Swagger los roles exclusivos de cada ruta: (Admin), (Librarian).

    Es idempotente: create_app() puede llamarse varias veces sobre los mismos routers.
    """
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        allowed = getattr(route.endpoint, "__roles__", frozenset())
        labels = [label for role, label in _LABELED_ROLES.items() if role in allowed]
        suffix = f" ({', '.join(labels)})"
        summary = route.summary or route.name.replace("_", " ").title()
        if labels and not summary.endswith(suffix):
            route.summary = summary + suffix
    return router
