from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno o de un archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://biblioteca:biblioteca@localhost:15432/biblioteca"
    jwt_secret: str = "cambia-este-secreto-de-al-menos-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    loan_days: int = 14
    librarian_name: str = "Bibliotecario"
    librarian_email: str = "bibliotecario@example.com"
    librarian_password: str = "bibliotecario123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
