"""Gestión de cuentas por rol (patrón AAA)."""

from uuid import uuid4

import pytest

from biblioteca.application.auth import Login, VerifyPrincipal
from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
)
from biblioteca.application.loans import BorrowBook, CloseLoan
from biblioteca.application.users import (
    CreateAccount,
    DeactivateAccount,
    GetAccount,
    ListAccounts,
    UpdateAccount,
)
from biblioteca.domain.entities import Principal, RoleName


@pytest.fixture
def as_principal(memory_uow):
    """Convierte una cuenta de prueba en el Principal que vendría en su token."""

    def build(account) -> Principal:
        with memory_uow:
            role = memory_uow.roles.get(account.user.role_id).name
        return Principal(user_id=account.user.id, role=role)

    return build


def _stored(uow, user_id):
    with uow:
        return uow.users.get(user_id)


# Crear


@pytest.mark.parametrize("role", [RoleName.LIBRARIAN, RoleName.USER])
def test_admin_creates_librarians_and_readers(memory_uow, hasher, admin, as_principal, role):
    # Arrange
    actor = as_principal(admin)

    # Act
    profile = CreateAccount(memory_uow, hasher).execute(
        actor, "Nueva", "nueva@example.com", "secreto123", role
    )

    # Assert
    assert profile.role == role
    assert profile.active is True
    assert _stored(memory_uow, profile.id).email == "nueva@example.com"


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (RoleName.ADMIN, RoleName.ADMIN),
        (RoleName.LIBRARIAN, RoleName.USER),
        (RoleName.LIBRARIAN, RoleName.LIBRARIAN),
        (RoleName.USER, RoleName.USER),
    ],
)
def test_only_admin_creates_accounts_and_never_admins(
    memory_uow, hasher, create_account, as_principal, actor_role, target_role
):
    # Arrange
    actor = as_principal(create_account(actor_role))

    # Act
    with pytest.raises(ForbiddenError):
        CreateAccount(memory_uow, hasher).execute(
            actor, "Nueva", "nueva@example.com", "secreto123", target_role
        )

    # Assert
    with memory_uow:
        assert memory_uow.users.get_by_email("nueva@example.com") is None


# Consultar


def test_admin_lists_librarians_and_readers_but_not_admins(
    memory_uow, admin, librarian, reader, create_account, as_principal
):
    # Arrange
    other_admin = create_account(RoleName.ADMIN)

    # Act
    profiles = ListAccounts(memory_uow).execute(as_principal(admin))

    # Assert
    ids = {p.id for p in profiles}
    assert ids == {librarian.user.id, reader.user.id}
    assert other_admin.user.id not in ids


def test_admin_filters_accounts_by_role(memory_uow, admin, librarian, reader, as_principal):
    # Arrange
    actor = as_principal(admin)

    # Act
    profiles = ListAccounts(memory_uow).execute(actor, RoleName.LIBRARIAN)

    # Assert
    assert [p.id for p in profiles] == [librarian.user.id]


@pytest.mark.parametrize("role", [RoleName.LIBRARIAN, RoleName.USER])
def test_non_admins_cannot_list_accounts(memory_uow, create_account, as_principal, role):
    # Arrange
    actor = as_principal(create_account(role))

    # Act / Assert
    with pytest.raises(ForbiddenError):
        ListAccounts(memory_uow).execute(actor)


def test_anyone_reads_their_own_account(memory_uow, librarian, as_principal):
    # Arrange
    actor = as_principal(librarian)

    # Act
    profile = GetAccount(memory_uow).execute(actor, librarian.user.id)

    # Assert
    assert profile.id == librarian.user.id
    assert profile.role == RoleName.LIBRARIAN


def test_reader_cannot_read_another_account(memory_uow, reader, create_account, as_principal):
    # Arrange
    other = create_account()

    # Act / Assert
    with pytest.raises(ForbiddenError):
        GetAccount(memory_uow).execute(as_principal(reader), other.user.id)


def test_unknown_account_returns_not_found(memory_uow, admin, as_principal):
    # Arrange
    unknown = uuid4()

    # Act / Assert
    with pytest.raises(NotFoundError):
        GetAccount(memory_uow).execute(as_principal(admin), unknown)


# Modificar


@pytest.mark.parametrize("role", [RoleName.LIBRARIAN, RoleName.USER])
def test_admin_updates_librarians_and_readers(
    memory_uow, hasher, admin, create_account, as_principal, role
):
    # Arrange
    target = create_account(role)

    # Act
    profile = UpdateAccount(memory_uow, hasher).execute(
        as_principal(admin), target.user.id, name=" Nuevo Nombre ", email="NUEVO@example.com"
    )

    # Assert
    assert profile.name == "Nuevo Nombre"
    assert profile.email == "nuevo@example.com"
    assert profile.role == role


def test_reader_updates_own_data_including_password(memory_uow, hasher, reader, as_principal):
    # Arrange
    actor = as_principal(reader)

    # Act
    UpdateAccount(memory_uow, hasher).execute(actor, reader.user.id, password="otraclave123")

    # Assert
    assert _stored(memory_uow, reader.user.id).password_hash == hasher.hash("otraclave123")


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (RoleName.USER, RoleName.USER),
        (RoleName.USER, RoleName.LIBRARIAN),
        (RoleName.LIBRARIAN, RoleName.USER),
        (RoleName.LIBRARIAN, RoleName.LIBRARIAN),
        (RoleName.ADMIN, RoleName.ADMIN),
    ],
)
def test_forbidden_updates_leave_the_account_untouched(
    memory_uow, hasher, create_account, as_principal, actor_role, target_role
):
    # Arrange
    actor = as_principal(create_account(actor_role))
    target = create_account(target_role)

    # Act
    with pytest.raises(ForbiddenError):
        UpdateAccount(memory_uow, hasher).execute(actor, target.user.id, name="Hackeado")

    # Assert
    assert _stored(memory_uow, target.user.id).name == "Cuenta"


@pytest.mark.parametrize("role", [RoleName.ADMIN, RoleName.LIBRARIAN])
def test_staff_cannot_edit_their_own_account(
    memory_uow, hasher, create_account, as_principal, role
):
    # Arrange
    account = create_account(role)

    # Act / Assert
    with pytest.raises(ForbiddenError):
        UpdateAccount(memory_uow, hasher).execute(
            as_principal(account), account.user.id, name="Otro"
        )


def test_update_rejects_an_email_taken_by_another_account(
    memory_uow, hasher, reader, create_account, as_principal
):
    # Arrange
    other = create_account()

    # Act / Assert
    with pytest.raises(ConflictError):
        UpdateAccount(memory_uow, hasher).execute(
            as_principal(reader), reader.user.id, email=other.user.email.upper()
        )


def test_update_never_changes_the_role(memory_uow, hasher, reader, as_principal):
    # Arrange
    role_before = _stored(memory_uow, reader.user.id).role_id

    # Act
    UpdateAccount(memory_uow, hasher).execute(as_principal(reader), reader.user.id, name="Ana")

    # Assert
    assert _stored(memory_uow, reader.user.id).role_id == role_before


# Desactivar


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (RoleName.ADMIN, RoleName.LIBRARIAN),
        (RoleName.ADMIN, RoleName.USER),
        (RoleName.LIBRARIAN, RoleName.USER),
    ],
)
def test_allowed_roles_deactivate_accounts(
    memory_uow, create_account, as_principal, actor_role, target_role
):
    # Arrange
    actor = as_principal(create_account(actor_role))
    target = create_account(target_role)

    # Act
    DeactivateAccount(memory_uow).execute(actor, target.user.id)

    # Assert
    assert _stored(memory_uow, target.user.id).active is False


def test_reader_deactivates_own_account(memory_uow, reader, as_principal):
    # Arrange
    actor = as_principal(reader)

    # Act
    DeactivateAccount(memory_uow).execute(actor, reader.user.id)

    # Assert
    assert _stored(memory_uow, reader.user.id).active is False


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (RoleName.USER, RoleName.USER),
        (RoleName.LIBRARIAN, RoleName.LIBRARIAN),
        (RoleName.LIBRARIAN, RoleName.ADMIN),
        (RoleName.ADMIN, RoleName.ADMIN),
    ],
)
def test_forbidden_deactivations_keep_the_account_active(
    memory_uow, create_account, as_principal, actor_role, target_role
):
    # Arrange
    actor = as_principal(create_account(actor_role))
    target = create_account(target_role)

    # Act
    with pytest.raises(ForbiddenError):
        DeactivateAccount(memory_uow).execute(actor, target.user.id)

    # Assert
    assert _stored(memory_uow, target.user.id).active is True


def test_account_with_open_loans_cannot_be_deactivated(memory_uow, librarian, reader, as_principal):
    # Arrange
    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1)
    BorrowBook(memory_uow).execute(reader.user.id, book.id)

    # Act
    with pytest.raises(BusinessRuleError):
        DeactivateAccount(memory_uow).execute(as_principal(reader), reader.user.id)

    # Assert
    assert _stored(memory_uow, reader.user.id).active is True


def test_deactivation_keeps_the_loan_history(memory_uow, librarian, reader, as_principal):
    # Arrange
    book = CreateBook(memory_uow).execute("Rayuela", "Cortázar", "978-1", 1)
    loan = BorrowBook(memory_uow).execute(reader.user.id, book.id)
    CloseLoan(memory_uow).execute(loan.id)

    # Act
    DeactivateAccount(memory_uow).execute(as_principal(librarian), reader.user.id)

    # Assert
    with memory_uow:
        assert [found.id for found in memory_uow.loans.list(user_id=reader.user.id)] == [loan.id]


def test_deactivating_twice_is_harmless(memory_uow, admin, reader, as_principal):
    # Arrange
    actor = as_principal(admin)
    DeactivateAccount(memory_uow).execute(actor, reader.user.id)

    # Act
    DeactivateAccount(memory_uow).execute(actor, reader.user.id)

    # Assert
    assert _stored(memory_uow, reader.user.id).active is False


# Efecto en la autenticación


def test_deactivated_account_cannot_log_in(memory_uow, hasher, token_service, reader, as_principal):
    # Arrange
    DeactivateAccount(memory_uow).execute(as_principal(reader), reader.user.id)

    # Act / Assert
    with pytest.raises(InvalidCredentialsError):
        Login(memory_uow, hasher, token_service).execute(reader.user.email, "secreto123")


def test_verify_principal_accepts_an_active_account(memory_uow, reader, as_principal):
    # Arrange
    principal = as_principal(reader)

    # Act
    result = VerifyPrincipal(memory_uow).execute(principal)

    # Assert
    assert result is None


@pytest.mark.parametrize("case", ["desactivada", "inexistente", "rol-distinto"])
def test_verify_principal_rejects_stale_tokens(memory_uow, reader, as_principal, case):
    # Arrange
    principal = as_principal(reader)
    if case == "desactivada":
        DeactivateAccount(memory_uow).execute(principal, reader.user.id)
    elif case == "inexistente":
        principal = Principal(user_id=uuid4(), role=RoleName.USER)
    else:
        principal = Principal(user_id=reader.user.id, role=RoleName.ADMIN)

    # Act / Assert
    with pytest.raises(InvalidTokenError):
        VerifyPrincipal(memory_uow).execute(principal)
