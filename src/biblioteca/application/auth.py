"""Casos de uso de autenticación: registro e inicio de sesión."""

from biblioteca.application.errors import (
    ConflictError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    required_text,
)
from biblioteca.domain.entities import Principal, RoleName, User
from biblioteca.domain.ports import PasswordHasher, TokenService, UnitOfWork


def normalize_email(email: str) -> str:
    return email.strip().lower()


class RegisterUser:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher) -> None:
        self.uow = uow
        self.hasher = hasher

    def execute(self, name: str, email: str, password: str, role: RoleName = RoleName.USER) -> User:
        name = required_text(name, "El nombre")
        email = normalize_email(email)
        with self.uow:
            if self.uow.users.get_by_email(email) is not None:
                raise ConflictError(f"Ya existe un usuario con el email {email}")
            stored_role = self.uow.roles.get_by_name(role)
            if stored_role is None:
                raise NotFoundError(f"No existe el rol {role}")

            user = User(
                name=name,
                email=email,
                password_hash=self.hasher.hash(password),
                role_id=stored_role.id,
            )
            self.uow.users.add(user)
            self.uow.commit()
            return user


class Login:
    """Valida las credenciales y emite un JWT con el rol leído de la tabla roles."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService) -> None:
        self.uow = uow
        self.hasher = hasher
        self.tokens = tokens

    def execute(self, email: str, password: str) -> str:
        with self.uow:
            user = self.uow.users.get_by_email(normalize_email(email))
            # El mismo error para email desconocido, clave errónea o cuenta desactivada:
            # no se revela cuál falló.
            if (
                user is None
                or not user.active
                or not self.hasher.verify(password, user.password_hash)
            ):
                raise InvalidCredentialsError("Email o contraseña incorrectos")
            role = self.uow.roles.get(user.role_id)
            return self.tokens.issue(Principal(user_id=user.id, role=role.name))


class VerifyPrincipal:
    """Comprueba que el dueño de un token sigue existiendo, activo y con el mismo rol.

    El JWT dura hasta que expira; sin esta comprobación una cuenta desactivada
    seguiría operando con su token hasta entonces.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, principal: Principal) -> None:
        with self.uow:
            user = self.uow.users.get(principal.user_id)
            if user is None or not user.active:
                raise InvalidTokenError("La cuenta no existe o está desactivada")
            if self.uow.roles.get(user.role_id).name != principal.role:
                raise InvalidTokenError("El rol del token ya no corresponde a la cuenta")
