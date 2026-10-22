"""Puertos del dominio.

Los casos de uso dependen solo de estas interfaces. Las de persistencia siguen el
patrón repositorio y viven en adapters/persistence: Postgres por defecto y una en
memoria para las pruebas. Las de seguridad viven en adapters/security.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from uuid import UUID

from biblioteca.domain.entities import (
    Book,
    Category,
    Loan,
    LoanModification,
    LoanStatus,
    Principal,
    Role,
    User,
)


class RoleRepository(ABC):
    @abstractmethod
    def add(self, role: Role) -> None: ...

    @abstractmethod
    def get(self, role_id: UUID) -> Role | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Role | None: ...


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None: ...

    @abstractmethod
    def get(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def update(self, user: User) -> None: ...

    @abstractmethod
    def list(self, role_ids: Iterable[UUID] | None = None) -> list[User]:
        """Ordenados por email; con role_ids solo los de esos roles."""


class CategoryRepository(ABC):
    @abstractmethod
    def add(self, category: Category) -> None: ...

    @abstractmethod
    def get(self, category_id: UUID) -> Category | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Category | None: ...

    @abstractmethod
    def list(self) -> list[Category]: ...


class BookRepository(ABC):
    @abstractmethod
    def add(self, book: Book) -> None: ...

    @abstractmethod
    def get(self, book_id: UUID, for_update: bool = False) -> Book | None:
        """Con for_update=True la fila queda bloqueada hasta el commit."""

    @abstractmethod
    def get_by_isbn(self, isbn: str) -> Book | None: ...

    @abstractmethod
    def update(self, book: Book) -> None: ...

    @abstractmethod
    def list_by_category(self, category_id: UUID) -> list[Book]: ...


class LoanRepository(ABC):
    @abstractmethod
    def add(self, loan: Loan) -> None: ...

    @abstractmethod
    def get(self, loan_id: UUID, for_update: bool = False) -> Loan | None: ...

    @abstractmethod
    def update(self, loan: Loan) -> None: ...

    @abstractmethod
    def list(
        self,
        user_id: UUID | None = None,
        book_id: UUID | None = None,
        statuses: Iterable[LoanStatus] | None = None,
    ) -> list[Loan]: ...


class LoanModificationRepository(ABC):
    """Historial de cambios de préstamos: solo se agrega y se consulta, nunca se edita."""

    @abstractmethod
    def add(self, modification: LoanModification) -> None: ...

    @abstractmethod
    def list_by_loan(self, loan_id: UUID) -> list[LoanModification]:
        """Del más antiguo al más reciente."""


class UnitOfWork(ABC):
    """Agrupa los repositorios en una transacción.

    Uso: `with uow: ...; uow.commit()`. Lo que no se confirme se revierte al salir.
    """

    roles: RoleRepository
    users: UserRepository
    categories: CategoryRepository
    books: BookRepository
    loans: LoanRepository
    loan_modifications: LoanModificationRepository

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, *exc_info) -> None:
        self.rollback()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(ABC):
    @abstractmethod
    def issue(self, principal: Principal) -> str: ...

    @abstractmethod
    def decode(self, token: str) -> Principal:
        """Devuelve el principal del token o lanza InvalidTokenError."""
