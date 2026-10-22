from uuid import uuid4

import jwt
import pytest

from biblioteca.adapters.security.bcrypt_hasher import BcryptPasswordHasher
from biblioteca.adapters.security.jwt_tokens import JwtTokenService
from biblioteca.application.errors import InvalidTokenError
from biblioteca.domain.entities import Principal

SECRET = "secreto-de-pruebas-con-32-bytes-o-mas"


def test_bcrypt_verifies_only_the_original_password():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("secreto123")

    assert hashed != "secreto123"
    assert hasher.verify("secreto123", hashed)
    assert not hasher.verify("otra", hashed)


def test_jwt_round_trip_keeps_user_and_role(token_service):
    principal = Principal(user_id=uuid4(), role="librarian")

    assert token_service.decode(token_service.issue(principal)) == principal


@pytest.mark.parametrize(
    "token",
    [
        "no-es-un-jwt",
        JwtTokenService(SECRET + "-otro").issue(Principal(uuid4(), "user")),
        JwtTokenService(SECRET, expires_minutes=-1).issue(Principal(uuid4(), "user")),
        jwt.encode({"sub": str(uuid4()), "exp": 9999999999}, SECRET),
        jwt.encode({"sub": "no-uuid", "role": "user", "exp": 9999999999}, SECRET),
    ],
    ids=["malformed", "wrong-secret", "expired", "missing-role", "bad-subject"],
)
def test_jwt_rejects_invalid_tokens(token_service, token):
    with pytest.raises(InvalidTokenError):
        token_service.decode(token)
