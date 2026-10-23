"""Los secretos no tienen valor por defecto: sin ellos la app no arranca (patrón AAA)."""

import pytest

from biblioteca.config import ConfigurationError, Settings, get_settings
from biblioteca.main import create_app

REQUIRED = ("DATABASE_URL", "JWT_SECRET", "LIBRARIAN_PASSWORD", "ADMIN_PASSWORD")


@pytest.fixture
def fresh_settings(monkeypatch):
    """Sin caché y sin leer un .env local, para ver solo el entorno de cada prueba."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("name", REQUIRED)
def test_missing_secret_is_rejected(fresh_settings, monkeypatch, name):
    # Arrange
    monkeypatch.delenv(name)

    # Act / Assert
    with pytest.raises(ConfigurationError, match=name):
        get_settings()


def test_short_jwt_secret_is_rejected(fresh_settings, monkeypatch):
    # Arrange
    monkeypatch.setenv("JWT_SECRET", "corto")

    # Act / Assert
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        get_settings()


def test_app_refuses_to_start_without_secrets(fresh_settings, monkeypatch):
    # Arrange
    for name in REQUIRED:
        monkeypatch.delenv(name)

    # Act / Assert
    with pytest.raises(
        ConfigurationError, match="ADMIN_PASSWORD, DATABASE_URL, JWT_SECRET, LIBRARIAN_PASSWORD"
    ):
        create_app()


def test_secrets_are_read_from_the_environment(fresh_settings, monkeypatch):
    # Arrange
    monkeypatch.setenv("JWT_SECRET", "x" * 32)

    # Act
    settings = get_settings()

    # Assert
    assert settings.jwt_secret == "x" * 32
