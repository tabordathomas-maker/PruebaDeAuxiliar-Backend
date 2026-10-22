from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from biblioteca.application.errors import InvalidTokenError
from biblioteca.domain.entities import Principal
from biblioteca.domain.ports import TokenService


class JwtTokenService(TokenService):
    def __init__(self, secret: str, algorithm: str = "HS256", expires_minutes: int = 60) -> None:
        self.secret = secret
        self.algorithm = algorithm
        self.expires = timedelta(minutes=expires_minutes)

    def issue(self, principal: Principal) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": str(principal.user_id),
            "role": principal.role,
            "iat": now,
            "exp": now + self.expires,
        }
        return jwt.encode(claims, self.secret, algorithm=self.algorithm)

    def decode(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"require": ["sub", "role", "exp"]},
            )
            return Principal(user_id=UUID(claims["sub"]), role=claims["role"])
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError("Token inválido o expirado") from exc
