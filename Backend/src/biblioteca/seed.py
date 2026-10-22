"""Crea el bibliotecario inicial si todavía no existe (`invoke seed`)."""

from biblioteca.adapters.http.dependencies import get_hasher, get_uow
from biblioteca.application.auth import RegisterUser
from biblioteca.application.errors import ConflictError
from biblioteca.config import get_settings
from biblioteca.domain.entities import RoleName


def seed_librarian() -> None:
    settings = get_settings()
    try:
        RegisterUser(get_uow(), get_hasher()).execute(
            settings.librarian_name,
            settings.librarian_email,
            settings.librarian_password,
            role=RoleName.LIBRARIAN,
        )
        print(f"Bibliotecario creado: {settings.librarian_email}")
    except ConflictError:
        print(f"El bibliotecario {settings.librarian_email} ya existe")


if __name__ == "__main__":
    seed_librarian()
