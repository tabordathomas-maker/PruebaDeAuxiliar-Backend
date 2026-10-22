"""Repositorios en memoria: misma interfaz que Postgres, sin base de datos.

Sirven para las pruebas de los casos de uso. La unidad de trabajo trabaja sobre
una copia del almacén y solo la publica al confirmar, igual que una transacción.
"""

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field, fields
from uuid import NAMESPACE_URL, UUID, uuid5

from biblioteca.domain.entities import Book, Category, Loan, LoanStatus, Role, RoleName, User
from biblioteca.domain.ports import (
    BookRepository,
    CategoryRepository,
    LoanRepository,
    RoleRepository,
    UnitOfWork,
    UserRepository,
)


def _base_roles() -> dict[UUID, Role]:
    roles = [Role(name=name, id=uuid5(NAMESPACE_URL, f"biblioteca:role:{name}")) for name in RoleName]
    return {role.id: role for role in roles}


@dataclass
class InMemoryStore:
    roles: dict[UUID, Role] = field(default_factory=_base_roles)
    users: dict[UUID, User] = field(default_factory=dict)
    categories: dict[UUID, Category] = field(default_factory=dict)
    books: dict[UUID, Book] = field(default_factory=dict)
    loans: dict[UUID, Loan] = field(default_factory=dict)


class _InMemoryRepository[T]:
    def __init__(self, items: dict[UUID, T]) -> None:
        self.items = items

    def add(self, entity: T) -> None:
        self.items[entity.id] = deepcopy(entity)

    def update(self, entity: T) -> None:
        self.items[entity.id] = deepcopy(entity)

    def get(self, entity_id: UUID, for_update: bool = False) -> T | None:
        return deepcopy(self.items.get(entity_id))

    def _find(self, **attrs) -> T | None:
        for item in self.items.values():
            if all(getattr(item, key) == value for key, value in attrs.items()):
                return deepcopy(item)
        return None


class InMemoryRoleRepository(_InMemoryRepository[Role], RoleRepository):
    def get_by_name(self, name: str) -> Role | None:
        return self._find(name=name)


class InMemoryUserRepository(_InMemoryRepository[User], UserRepository):
    def get_by_email(self, email: str) -> User | None:
        return self._find(email=email)


class InMemoryCategoryRepository(_InMemoryRepository[Category], CategoryRepository):
    def get_by_name(self, name: str) -> Category | None:
        return self._find(name=name)

    def list(self) -> list[Category]:
        return sorted(deepcopy(list(self.items.values())), key=lambda c: c.name)


class InMemoryBookRepository(_InMemoryRepository[Book], BookRepository):
    def get_by_isbn(self, isbn: str) -> Book | None:
        return self._find(isbn=isbn)

    def list_by_category(self, category_id: UUID) -> list[Book]:
        books = [b for b in self.items.values() if category_id in b.category_ids]
        return sorted(deepcopy(books), key=lambda b: b.title)


class InMemoryLoanRepository(_InMemoryRepository[Loan], LoanRepository):
    def list(
        self,
        user_id: UUID | None = None,
        book_id: UUID | None = None,
        statuses: Iterable[LoanStatus] | None = None,
    ) -> list[Loan]:
        wanted = set(statuses) if statuses is not None else None
        loans = [
            loan
            for loan in self.items.values()
            if (user_id is None or loan.user_id == user_id)
            and (book_id is None or loan.book_id == book_id)
            and (wanted is None or loan.status in wanted)
        ]
        # Mismo orden que Postgres: primero los que no tienen fecha de salida y
        # después los más recientes; a igual fecha, por id.
        undated = sorted((l for l in loans if l.loaned_at is None), key=lambda l: l.id)
        dated = sorted((l for l in loans if l.loaned_at is not None), key=lambda l: l.id)
        dated.sort(key=lambda l: l.loaned_at, reverse=True)
        return deepcopy(undated + dated)


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()
        self.committed = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        self._begin()
        return self

    def commit(self) -> None:
        # Se muta el almacén en lugar de reemplazarlo: otras unidades de trabajo
        # que lo comparten (una por petición HTTP) ven los cambios.
        for item in fields(InMemoryStore):
            setattr(self.store, item.name, getattr(self._working, item.name))
        self.committed = True
        self._begin()

    def rollback(self) -> None:
        self._begin()

    def _begin(self) -> None:
        self._working = deepcopy(self.store)
        self.roles = InMemoryRoleRepository(self._working.roles)
        self.users = InMemoryUserRepository(self._working.users)
        self.categories = InMemoryCategoryRepository(self._working.categories)
        self.books = InMemoryBookRepository(self._working.books)
        self.loans = InMemoryLoanRepository(self._working.loans)
