from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno o de un archivo .env.

    Los secretos (URL de la base con su clave, firma de los tokens y claves de las cuentas
    iniciales) no tienen valor por defecto: el repositorio es público y un valor escrito
    aquí permitiría fabricar tokens o entrar a la base. Si faltan, la aplicación no arranca.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(min_length=1)
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    loan_days: int = 14
    librarian_name: str = "Bibliotecario"
    librarian_email: str = "bibliotecario@example.com"
    librarian_password: str = Field(min_length=8)
    admin_name: str = "Administrador"
    admin_email: str = "admin@example.com"
    admin_password: str = Field(min_length=8)


class ConfigurationError(RuntimeError):
    """Falta una variable obligatoria o tiene un valor inválido."""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        names = sorted({str(e["loc"][0]).upper() for e in error.errors()})
        raise ConfigurationError(
            f"Configuración incompleta o inválida: {', '.join(names)}. "
            "Defínelas en el entorno o en .env (`invoke env` lo genera)."
        ) from None
