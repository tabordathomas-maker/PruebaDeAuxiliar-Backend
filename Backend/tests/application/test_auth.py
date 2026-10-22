import pytest

from biblioteca.application.auth import Login, RegisterUser
from biblioteca.application.errors import ConflictError, InvalidCredentialsError
from biblioteca.domain.entities import Principal, RoleName
from biblioteca.domain.ports import PasswordHasher, TokenService


@pytest.fixture
def mock_hasher(mocker):
    hasher = mocker.Mock(spec=PasswordHasher)
    hasher.hash.return_value = "hashed"
    return hasher


@pytest.fixture
def mock_tokens(mocker):
    tokens = mocker.Mock(spec=TokenService)
    tokens.issue.return_value = "signed-token"
    return tokens


def test_register_creates_user_with_user_role_and_hashed_password(memory_uow, mock_hasher):
    user = RegisterUser(memory_uow, mock_hasher).execute("Ana", " Ana@Example.com ", "secreto123")

    mock_hasher.hash.assert_called_once_with("secreto123")
    with memory_uow:
        stored = memory_uow.users.get(user.id)
        assert stored.email == "ana@example.com"
        assert stored.password_hash == "hashed"
        assert memory_uow.roles.get(stored.role_id).name == RoleName.USER


def test_register_can_create_a_librarian(memory_uow, mock_hasher):
    user = RegisterUser(memory_uow, mock_hasher).execute(
        "Luz", "luz@example.com", "secreto123", role=RoleName.LIBRARIAN
    )

    with memory_uow:
        assert memory_uow.roles.get(user.role_id).name == RoleName.LIBRARIAN


def test_register_rejects_duplicate_email_ignoring_case(memory_uow, mock_hasher):
    register = RegisterUser(memory_uow, mock_hasher)
    register.execute("Ana", "ana@example.com", "secreto123")

    with pytest.raises(ConflictError):
        register.execute("Otra Ana", "ANA@example.com", "secreto456")


def test_login_issues_token_with_role_read_from_roles_table(
    memory_uow, hasher, mock_tokens
):
    user = RegisterUser(memory_uow, hasher).execute("Ana", "ana@example.com", "secreto123")

    token = Login(memory_uow, hasher, mock_tokens).execute("ana@example.com", "secreto123")

    assert token == "signed-token"
    mock_tokens.issue.assert_called_once_with(Principal(user_id=user.id, role=RoleName.USER))


@pytest.mark.parametrize(
    ("email", "password"),
    [("ana@example.com", "incorrecta"), ("nadie@example.com", "secreto123")],
)
def test_login_rejects_bad_credentials(memory_uow, hasher, mock_tokens, email, password):
    RegisterUser(memory_uow, hasher).execute("Ana", "ana@example.com", "secreto123")

    with pytest.raises(InvalidCredentialsError):
        Login(memory_uow, hasher, mock_tokens).execute(email, password)

    mock_tokens.issue.assert_not_called()
