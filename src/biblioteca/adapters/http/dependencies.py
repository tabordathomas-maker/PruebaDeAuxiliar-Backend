"""Cableado de los adaptadores por defecto.

Las rutas piden estas dependencias a FastAPI; las pruebas las sustituyen con
`app.dependency_overrides`, por ejemplo por la unidad de trabajo en memoria.
"""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from biblioteca.adapters.persistence.postgres.repositories import (
    PostgresUnitOfWork,
    build_session_factory,
)
from biblioteca.adapters.security.bcrypt_hasher import BcryptPasswordHasher
from biblioteca.adapters.security.jwt_tokens import JwtTokenService
from biblioteca.config import get_settings
from biblioteca.domain.ports import PasswordHasher, TokenService, UnitOfWork


@lru_cache
def _session_factory() -> sessionmaker:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return build_session_factory(engine)


def get_uow() -> UnitOfWork:
    return PostgresUnitOfWork(_session_factory())


def get_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expires_minutes
    )
