"""Repositorios relacionales sobre Postgres (implementación por defecto)."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from biblioteca.adapters.persistence.postgres import tables as t
from biblioteca.domain.entities import Book, Category, Loan, LoanStatus, Role, User
from biblioteca.domain.ports import (
    BookRepository,
    CategoryRepository,
    LoanRepository,
    RoleRepository,
    UnitOfWork,
    UserRepository,
)


class PostgresRoleRepository(RoleRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, role: Role) -> None:
        self.session.execute(insert(t.roles).values(id=role.id, name=role.name))

    def get(self, role_id: UUID) -> Role | None:
        return self._one(t.roles.c.id == role_id)

    def get_by_name(self, name: str) -> Role | None:
        return self._one(t.roles.c.name == name)

    def _one(self, condition) -> Role | None:
        row = self.session.execute(select(t.roles).where(condition)).one_or_none()
        return Role(id=row.id, name=row.name) if row else None


class PostgresUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: User) -> None:
        self.session.execute(
            insert(t.users).values(
                id=user.id,
                name=user.name,
                email=user.email,
                password_hash=user.password_hash,
                role_id=user.role_id,
            )
        )

    def get(self, user_id: UUID) -> User | None:
        return self._one(t.users.c.id == user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._one(t.users.c.email == email)

    def _one(self, condition) -> User | None:
        row = self.session.execute(select(t.users).where(condition)).one_or_none()
        if row is None:
            return None
        return User(
            id=row.id,
            name=row.name,
            email=row.email,
            password_hash=row.password_hash,
            role_id=row.role_id,
        )


class PostgresCategoryRepository(CategoryRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, category: Category) -> None:
        self.session.execute(insert(t.categories).values(id=category.id, name=category.name))

    def get(self, category_id: UUID) -> Category | None:
        return self._one(t.categories.c.id == category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self._one(t.categories.c.name == name)

    def list(self) -> list[Category]:
        rows = self.session.execute(select(t.categories).order_by(t.categories.c.name))
        return [Category(id=row.id, name=row.name) for row in rows]

    def _one(self, condition) -> Category | None:
        row = self.session.execute(select(t.categories).where(condition)).one_or_none()
        return Category(id=row.id, name=row.name) if row else None


class PostgresBookRepository(BookRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, book: Book) -> None:
        self.session.execute(insert(t.books).values(**self._columns(book)))
        self._insert_categories(book.id, book.category_ids)

    def get(self, book_id: UUID, for_update: bool = False) -> Book | None:
        query = select(t.books).where(t.books.c.id == book_id)
        if for_update:
            query = query.with_for_update()
        row = self.session.execute(query).one_or_none()
        return self._to_entity(row) if row else None

    def get_by_isbn(self, isbn: str) -> Book | None:
        row = self.session.execute(select(t.books).where(t.books.c.isbn == isbn)).one_or_none()
        return self._to_entity(row) if row else None

    def update(self, book: Book) -> None:
        self.session.execute(
            update(t.books).where(t.books.c.id == book.id).values(**self._columns(book))
        )
        self.session.execute(delete(t.book_categories).where(t.book_categories.c.book_id == book.id))
        self._insert_categories(book.id, book.category_ids)

    def list_by_category(self, category_id: UUID) -> list[Book]:
        query = (
            select(t.books)
            .join(t.book_categories, t.book_categories.c.book_id == t.books.c.id)
            .where(t.book_categories.c.category_id == category_id)
            .order_by(t.books.c.title)
        )
        return [self._to_entity(row) for row in self.session.execute(query)]

    def _insert_categories(self, book_id: UUID, category_ids: set[UUID]) -> None:
        if category_ids:
            self.session.execute(
                insert(t.book_categories),
                [{"book_id": book_id, "category_id": cid} for cid in category_ids],
            )

    def _to_entity(self, row) -> Book:
        category_ids = self.session.scalars(
            select(t.book_categories.c.category_id).where(t.book_categories.c.book_id == row.id)
        )
        return Book(
            id=row.id,
            title=row.title,
            author=row.author,
            isbn=row.isbn,
            total_copies=row.total_copies,
            available_copies=row.available_copies,
            category_ids=set(category_ids),
        )

    @staticmethod
    def _columns(book: Book) -> dict:
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "isbn": book.isbn,
            "total_copies": book.total_copies,
            "available_copies": book.available_copies,
        }


class PostgresLoanRepository(LoanRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, loan: Loan) -> None:
        self.session.execute(insert(t.loans).values(**self._columns(loan)))

    def get(self, loan_id: UUID, for_update: bool = False) -> Loan | None:
        query = select(t.loans).where(t.loans.c.id == loan_id)
        if for_update:
            query = query.with_for_update()
        row = self.session.execute(query).one_or_none()
        return self._to_entity(row) if row else None

    def update(self, loan: Loan) -> None:
        self.session.execute(
            update(t.loans).where(t.loans.c.id == loan.id).values(**self._columns(loan))
        )

    def list(
        self,
        user_id: UUID | None = None,
        book_id: UUID | None = None,
        statuses: Iterable[LoanStatus] | None = None,
    ) -> list[Loan]:
        query = select(t.loans)
        if user_id is not None:
            query = query.where(t.loans.c.user_id == user_id)
        if book_id is not None:
            query = query.where(t.loans.c.book_id == book_id)
        if statuses is not None:
            query = query.where(t.loans.c.status.in_(list(statuses)))
        query = query.order_by(t.loans.c.loaned_at.desc().nulls_first(), t.loans.c.id)
        return [self._to_entity(row) for row in self.session.execute(query)]

    @staticmethod
    def _to_entity(row) -> Loan:
        return Loan(
            id=row.id,
            user_id=row.user_id,
            book_id=row.book_id,
            status=row.status,
            loaned_at=row.loaned_at,
            due_at=row.due_at,
            returned_at=row.returned_at,
        )

    @staticmethod
    def _columns(loan: Loan) -> dict:
        return {
            "id": loan.id,
            "user_id": loan.user_id,
            "book_id": loan.book_id,
            "status": loan.status,
            "loaned_at": loan.loaned_at,
            "due_at": loan.due_at,
            "returned_at": loan.returned_at,
        }


class PostgresUnitOfWork(UnitOfWork):
    """Abre una sesión por bloque `with`; los repositorios comparten su transacción."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> "PostgresUnitOfWork":
        self.session = self.session_factory()
        self.roles = PostgresRoleRepository(self.session)
        self.users = PostgresUserRepository(self.session)
        self.categories = PostgresCategoryRepository(self.session)
        self.books = PostgresBookRepository(self.session)
        self.loans = PostgresLoanRepository(self.session)
        return self

    def __exit__(self, *exc_info) -> None:
        super().__exit__(*exc_info)
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


def build_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
