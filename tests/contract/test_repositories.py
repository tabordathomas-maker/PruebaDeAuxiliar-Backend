"""Contrato común de los repositorios: cualquier implementación debe pasarlo."""

from datetime import UTC, datetime, timedelta

import pytest

from biblioteca.domain.entities import Book, Category, Loan, LoanStatus, RoleName, User


def _seed_user(uow, email="ana@example.com") -> User:
    role = uow.roles.get_by_name(RoleName.USER)
    user = User(name="Ana", email=email, password_hash="hash", role_id=role.id)
    uow.users.add(user)
    return user


def _seed_book(uow, isbn="978-1", copies=2, category_ids=()) -> Book:
    book = Book("Rayuela", "Cortázar", isbn, copies, copies, set(category_ids))
    uow.books.add(book)
    return book


def test_base_roles_exist(uow):
    with uow:
        assert uow.roles.get_by_name(RoleName.LIBRARIAN) is not None
        assert uow.roles.get_by_name(RoleName.USER) is not None


def test_user_is_found_by_email_after_commit(uow):
    with uow:
        user = _seed_user(uow)
        uow.commit()

    with uow:
        assert uow.users.get_by_email("ana@example.com") == user
        assert uow.users.get(user.id) == user


def test_uncommitted_changes_are_discarded(uow):
    with uow:
        _seed_user(uow)

    with uow:
        assert uow.users.get_by_email("ana@example.com") is None


def test_books_and_categories_are_many_to_many(uow):
    novel, classic = Category("Novela"), Category("Clásico")
    with uow:
        uow.categories.add(novel)
        uow.categories.add(classic)
        rayuela = _seed_book(uow, "978-1", category_ids={novel.id, classic.id})
        _seed_book(uow, "978-2", category_ids={novel.id})
        uow.commit()

    with uow:
        assert uow.books.get(rayuela.id).category_ids == {novel.id, classic.id}
        assert len(uow.books.list_by_category(novel.id)) == 2
        assert [b.id for b in uow.books.list_by_category(classic.id)] == [rayuela.id]
        assert uow.categories.get_by_name("Novela") == novel
        assert {c.name for c in uow.categories.list()} == {"Novela", "Clásico"}


def test_book_update_persists_copies_and_categories(uow):
    novel = Category("Novela")
    with uow:
        uow.categories.add(novel)
        book = _seed_book(uow)
        uow.commit()

    with uow:
        stored = uow.books.get(book.id, for_update=True)
        stored.available_copies = 1
        stored.category_ids = {novel.id}
        uow.books.update(stored)
        uow.commit()

    with uow:
        assert uow.books.get_by_isbn("978-1").available_copies == 1
        assert uow.books.get(book.id).category_ids == {novel.id}


def test_loans_belong_to_one_user_and_one_book(uow):
    with uow:
        ana = _seed_user(uow)
        luis = _seed_user(uow, "luis@example.com")
        book = _seed_book(uow)
        pending = Loan(user_id=ana.id, book_id=book.id)
        now = datetime.now(UTC)
        active = Loan(
            user_id=ana.id,
            book_id=book.id,
            status=LoanStatus.ACTIVE,
            loaned_at=now,
            due_at=now + timedelta(days=14),
        )
        other = Loan(user_id=luis.id, book_id=book.id)
        for loan in (pending, active, other):
            uow.loans.add(loan)
        uow.commit()

    with uow:
        assert {found.id for found in uow.loans.list(user_id=ana.id)} == {pending.id, active.id}
        assert len(uow.loans.list(book_id=book.id)) == 3
        assert [found.id for found in uow.loans.list(statuses=[LoanStatus.ACTIVE])] == [active.id]
        assert uow.loans.get(active.id) == active


def test_loan_update_persists_status_and_dates(uow):
    with uow:
        user = _seed_user(uow)
        book = _seed_book(uow)
        loan = Loan(user_id=user.id, book_id=book.id)
        uow.loans.add(loan)
        uow.commit()

    returned_at = datetime.now(UTC)
    with uow:
        stored = uow.loans.get(loan.id, for_update=True)
        stored.status = LoanStatus.RETURNED
        stored.returned_at = returned_at
        uow.loans.update(stored)
        uow.commit()

    with uow:
        assert uow.loans.get(loan.id).status is LoanStatus.RETURNED
        assert uow.loans.get(loan.id).returned_at == returned_at


def test_loan_request_date_is_persisted(uow):
    # Arrange
    requested = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)
    with uow:
        user = _seed_user(uow)
        book = _seed_book(uow)
        loan = Loan(user_id=user.id, book_id=book.id, requested_at=requested)

        # Act
        uow.loans.add(loan)
        uow.commit()

    # Assert
    with uow:
        assert uow.loans.get(loan.id).requested_at == requested


@pytest.mark.parametrize("missing", ["user", "book", "category", "loan"])
def test_unknown_ids_return_none(uow, missing):
    from uuid import uuid4

    repo = {"user": "users", "book": "books", "category": "categories", "loan": "loans"}[missing]
    with uow:
        assert getattr(uow, repo).get(uuid4()) is None
