"""Crea el administrador y el bibliotecario iniciales si todavía no existen (`invoke seed`)."""

from biblioteca.adapters.http.dependencies import get_hasher, get_uow
from biblioteca.application.auth import RegisterUser
from biblioteca.application.errors import ConflictError
from biblioteca.config import get_settings
from biblioteca.domain.entities import RoleName


def _seed(name: str, email: str, password: str, role: RoleName, label: str) -> None:
    try:
        RegisterUser(get_uow(), get_hasher()).execute(name, email, password, role=role)
        print(f"{label} creado: {email}")
    except ConflictError:
        print(f"El {label.lower()} {email} ya existe")


def seed_accounts() -> None:
    settings = get_settings()
    # Los administradores solo se crean aquí: la API no permite crearlos.
    _seed(
        settings.admin_name,
        settings.admin_email,
        settings.admin_password,
        RoleName.ADMIN,
        "Administrador",
    )
    _seed(
        settings.librarian_name,
        settings.librarian_email,
        settings.librarian_password,
        RoleName.LIBRARIAN,
        "Bibliotecario",
    )


if __name__ == "__main__":
    seed_accounts()
