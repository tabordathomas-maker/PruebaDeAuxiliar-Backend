"""Casos de uso de gestión de cuentas.

Permisos:
- El administrador crea, consulta, modifica y desactiva bibliotecarios y lectores.
  No gestiona a otros administradores: esos se crean con el seed.
- El bibliotecario solo desactiva lectores.
- El lector consulta, modifica y da de baja su propia cuenta.
Nadie cambia roles por la API. Las bajas son lógicas (`active = False`) para no
perder préstamos ni auditorías.
"""

from dataclasses import dataclass
from uuid import UUID

from biblioteca.application.auth import RegisterUser, normalize_email
from biblioteca.application.errors import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    required_text,
)
from biblioteca.application.loans import OPEN_STATUSES
from biblioteca.domain.entities import Principal, RoleName, User
from biblioteca.domain.ports import PasswordHasher, UnitOfWork

# Roles de las cuentas ajenas que cada rol puede crear, consultar y modificar.
MANAGEABLE_ROLES: dict[str, frozenset[RoleName]] = {
    RoleName.ADMIN: frozenset({RoleName.LIBRARIAN, RoleName.USER}),
}
# Roles de las cuentas ajenas que cada rol puede desactivar.
DEACTIVATABLE_ROLES: dict[str, frozenset[RoleName]] = {
    RoleName.ADMIN: frozenset({RoleName.LIBRARIAN, RoleName.USER}),
    RoleName.LIBRARIAN: frozenset({RoleName.USER}),
}
# Roles que administran su propia cuenta (modificarla y darse de baja).
SELF_SERVICE_ROLES = frozenset({RoleName.USER})


@dataclass(frozen=True)
class UserProfile:
    id: UUID
    name: str
    email: str
    role: str
    active: bool


def _profile(uow: UnitOfWork, user: User) -> UserProfile:
    role = uow.roles.get(user.role_id)
    return UserProfile(user.id, user.name, user.email, role.name, user.active)


def _load_target(
    uow: UnitOfWork,
    actor: Principal,
    user_id: UUID,
    allowed: dict[str, frozenset[RoleName]],
) -> User:
    """La cuenta sobre la que actúa `actor`, si sus permisos se lo permiten."""
    user = uow.users.get(user_id)
    if user is None:
        raise NotFoundError("La cuenta no existe")
    if user.id == actor.user_id and actor.role in SELF_SERVICE_ROLES:
        return user
    target_role = uow.roles.get(user.role_id).name
    if user.id == actor.user_id or target_role not in allowed.get(actor.role, frozenset()):
        raise ForbiddenError("Tu rol no puede gestionar esta cuenta")
    return user


class CreateAccount:
    """El administrador crea bibliotecarios y lectores."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher) -> None:
        self.uow = uow
        self.hasher = hasher

    def execute(
        self, actor: Principal, name: str, email: str, password: str, role: RoleName
    ) -> UserProfile:
        if role not in MANAGEABLE_ROLES.get(actor.role, frozenset()):
            raise ForbiddenError(f"Tu rol no puede crear cuentas con rol {role}")
        user = RegisterUser(self.uow, self.hasher).execute(name, email, password, role=role)
        with self.uow:
            return _profile(self.uow, user)


class ListAccounts:
    """El administrador lista las cuentas que gestiona, activas o no."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, actor: Principal, role: RoleName | None = None) -> list[UserProfile]:
        manageable = MANAGEABLE_ROLES.get(actor.role, frozenset())
        if not manageable:
            raise ForbiddenError("Tu rol no puede consultar cuentas")
        wanted = manageable if role is None else manageable & {role}
        with self.uow:
            role_ids = [self.uow.roles.get_by_name(name).id for name in wanted]
            return [_profile(self.uow, u) for u in self.uow.users.list(role_ids=role_ids)]


class GetAccount:
    """Los datos de una cuenta: la propia para cualquiera, la ajena si se gestiona."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, actor: Principal, user_id: UUID) -> UserProfile:
        with self.uow:
            if user_id == actor.user_id:
                user = self.uow.users.get(user_id)
                if user is None:
                    raise NotFoundError("La cuenta no existe")
            else:
                user = _load_target(self.uow, actor, user_id, MANAGEABLE_ROLES)
            return _profile(self.uow, user)


class UpdateAccount:
    """Modifica nombre, email o contraseña. El rol y el estado no se cambian por aquí."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher) -> None:
        self.uow = uow
        self.hasher = hasher

    def execute(
        self,
        actor: Principal,
        user_id: UUID,
        name: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> UserProfile:
        with self.uow:
            user = _load_target(self.uow, actor, user_id, MANAGEABLE_ROLES)
            if name is not None:
                user.name = required_text(name, "El nombre")
            if email is not None:
                email = normalize_email(email)
                owner = self.uow.users.get_by_email(email)
                if owner is not None and owner.id != user.id:
                    raise ConflictError(f"Ya existe un usuario con el email {email}")
                user.email = email
            if password is not None:
                user.password_hash = self.hasher.hash(password)
            self.uow.users.update(user)
            self.uow.commit()
            return _profile(self.uow, user)


class DeactivateAccount:
    """Baja lógica de una cuenta: deja de poder iniciar sesión y sus tokens dejan de valer.

    Se niega si la cuenta tiene préstamos abiertos, para no dejar libros reservados
    o prestados a nombre de una cuenta que ya no responde.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, actor: Principal, user_id: UUID) -> None:
        with self.uow:
            user = _load_target(self.uow, actor, user_id, DEACTIVATABLE_ROLES)
            if not user.active:
                return
            if self.uow.loans.list(user_id=user.id, statuses=OPEN_STATUSES):
                raise BusinessRuleError(
                    "La cuenta tiene préstamos abiertos; deben cerrarse antes de darla de baja"
                )
            user.active = False
            self.uow.users.update(user)
            self.uow.commit()
