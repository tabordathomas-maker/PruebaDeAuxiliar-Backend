"""Contrato de cuentas y auditoría: corre contra memoria y Postgres (patrón AAA)."""

from datetime import UTC, datetime, timedelta

from biblioteca.domain.entities import Book, Loan, LoanModification, LoanStatus, RoleName, User

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _seed_user(uow, email="ana@example.com", role=RoleName.USER) -> User:
    user = User("Ana", email, "hash", uow.roles.get_by_name(role).id)
    uow.users.add(user)
    return user


def _seed_loan(uow, user) -> Loan:
    book = Book("Rayuela", "Cortázar", "978-1", 1, 0)
    uow.books.add(book)
    loan = Loan(
        user_id=user.id,
        book_id=book.id,
        status=LoanStatus.ACTIVE,
        loaned_at=NOW,
        due_at=NOW + timedelta(days=14),
    )
    uow.loans.add(loan)
    return loan


def _modification(loan, actor, minutes=0, new_due="2026-11-20T12:00:00+00:00"):
    return LoanModification(
        loan_id=loan.id,
        modified_by=actor.id,
        modified_at=NOW + timedelta(minutes=minutes),
        changed_fields=["due_at"],
        old_values={"due_at": "2026-11-05T12:00:00+00:00"},
        new_values={"due_at": new_due},
        reason="Renovación",
    )


def test_admin_role_exists(uow):
    # Arrange
    name = RoleName.ADMIN

    # Act
    with uow:
        admin = uow.roles.get_by_name(name)

    # Assert
    assert admin is not None


def test_new_users_are_active_and_deactivation_persists(uow):
    # Arrange
    with uow:
        user = _seed_user(uow)
        uow.commit()

    # Act
    with uow:
        stored = uow.users.get(user.id)
        stored.active = False
        stored.name = "Ana María"
        uow.users.update(stored)
        uow.commit()

    # Assert
    with uow:
        reloaded = uow.users.get(user.id)
        assert user.active is True
        assert (reloaded.active, reloaded.name) == (False, "Ana María")


def test_users_are_listed_by_email_and_filtered_by_role(uow):
    # Arrange
    with uow:
        zoe = _seed_user(uow, "zoe@example.com")
        ana = _seed_user(uow, "ana@example.com")
        luz = _seed_user(uow, "luz@example.com", RoleName.LIBRARIAN)
        librarian_role = uow.roles.get_by_name(RoleName.LIBRARIAN).id
        uow.commit()

    # Act
    with uow:
        everyone = uow.users.list()
        librarians = uow.users.list(role_ids=[librarian_role])

    # Assert
    assert [u.id for u in everyone] == [ana.id, luz.id, zoe.id]
    assert [u.id for u in librarians] == [luz.id]


def test_modifications_are_stored_with_all_their_data(uow):
    # Arrange
    with uow:
        reader = _seed_user(uow)
        librarian = _seed_user(uow, "luz@example.com", RoleName.LIBRARIAN)
        loan = _seed_loan(uow, reader)
        modification = _modification(loan, librarian)
        uow.commit()

    # Act
    with uow:
        uow.loan_modifications.add(modification)
        uow.commit()

    # Assert
    with uow:
        assert uow.loan_modifications.list_by_loan(loan.id) == [modification]


def test_each_modification_is_an_independent_record_in_order(uow):
    # Arrange
    with uow:
        reader = _seed_user(uow)
        loan = _seed_loan(uow, reader)
        later = _modification(loan, reader, minutes=5, new_due="2026-11-25T12:00:00+00:00")
        earlier = _modification(loan, reader, minutes=0)
        uow.commit()

    # Act
    with uow:
        uow.loan_modifications.add(later)
        uow.loan_modifications.add(earlier)
        uow.commit()

    # Assert
    with uow:
        assert [m.id for m in uow.loan_modifications.list_by_loan(loan.id)] == [
            earlier.id,
            later.id,
        ]


def test_uncommitted_modifications_are_discarded(uow):
    # Arrange
    with uow:
        reader = _seed_user(uow)
        loan = _seed_loan(uow, reader)
        uow.commit()

    # Act
    with uow:
        uow.loan_modifications.add(_modification(loan, reader))

    # Assert
    with uow:
        assert uow.loan_modifications.list_by_loan(loan.id) == []


def test_history_survives_deactivating_its_author(uow):
    # Arrange
    with uow:
        reader = _seed_user(uow)
        librarian = _seed_user(uow, "luz@example.com", RoleName.LIBRARIAN)
        loan = _seed_loan(uow, reader)
        uow.loan_modifications.add(_modification(loan, librarian))
        uow.commit()

    # Act
    with uow:
        for user_id in (reader.id, librarian.id):
            user = uow.users.get(user_id)
            user.active = False
            uow.users.update(user)
        uow.commit()

    # Assert
    with uow:
        [kept] = uow.loan_modifications.list_by_loan(loan.id)
        assert kept.modified_by == librarian.id
