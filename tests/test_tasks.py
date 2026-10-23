"""`invoke env`: crea o completa el .env sin salir de la carpeta del proyecto (patrón AAA)."""

import pytest
from invoke import Context

import tasks

TEMPLATE = """# Plantilla
POSTGRES_USER=biblioteca
POSTGRES_PASSWORD=
POSTGRES_DB=biblioteca
DATABASE_URL=
JWT_SECRET=
LOAN_DAYS=14
"""


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Un proyecto falso con su .env.example, para no tocar el .env real."""
    monkeypatch.setattr(tasks, "ROOT", tmp_path.resolve())
    (tmp_path / ".env.example").write_text(TEMPLATE, encoding="utf-8")
    return tmp_path


def read_env(root):
    return tasks.parse_env((root / ".env").read_text(encoding="utf-8"))


def test_env_creates_the_file_with_random_secrets(root):
    # Act
    tasks.env(Context())

    # Assert
    values = read_env(root)
    password = values["POSTGRES_PASSWORD"]
    assert len(password) >= 32
    assert len(values["JWT_SECRET"]) >= 32
    assert values["DATABASE_URL"] == (
        f"postgresql+psycopg://biblioteca:{password}@localhost:15432/biblioteca"
    )
    assert values["LOAN_DAYS"] == "14"
    assert (root / ".env").read_text(encoding="utf-8").startswith("# Plantilla\n")


def test_env_completes_an_existing_file_without_changing_its_values(root):
    # Arrange
    existing = "DATABASE_URL=postgresql+psycopg://biblioteca:clave-vieja@localhost:15432/biblioteca\nJWT_SECRET=propio\n"
    (root / ".env").write_text(existing, encoding="utf-8")

    # Act
    tasks.env(Context())

    # Assert
    content = (root / ".env").read_text(encoding="utf-8")
    values = tasks.parse_env(content)
    assert content.startswith(existing)
    assert values["JWT_SECRET"] == "propio"
    assert values["POSTGRES_PASSWORD"] == "clave-vieja"
    assert values["POSTGRES_USER"] == "biblioteca"


def test_env_leaves_a_complete_file_untouched(root):
    # Arrange
    tasks.env(Context())
    before = (root / ".env").read_text(encoding="utf-8")

    # Act
    tasks.env(Context())

    # Assert
    assert (root / ".env").read_text(encoding="utf-8") == before


def test_env_rejects_a_symlink_that_points_outside_the_project(root, tmp_path_factory):
    # Arrange
    outside = tmp_path_factory.mktemp("fuera") / "objetivo"
    outside.write_text("", encoding="utf-8")
    try:
        (root / ".env").symlink_to(outside)
    except OSError:
        pytest.skip("El sistema no permite crear enlaces simbólicos")

    # Act / Assert
    with pytest.raises(ValueError, match="carpeta del proyecto"):
        tasks.env(Context())
    assert outside.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("name", ["../.env", "sub/.env"])
def test_project_file_rejects_paths_outside_the_root(root, name):
    # Act / Assert
    with pytest.raises(ValueError, match="carpeta del proyecto"):
        tasks.project_file(name)


def test_env_rejects_an_invalid_template(root):
    # Arrange
    (root / ".env.example").write_text("../../etc/passwd\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="Línea inválida"):
        tasks.env(Context())
    assert not (root / ".env").exists()
