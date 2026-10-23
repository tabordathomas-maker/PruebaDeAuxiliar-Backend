import re
import secrets
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from invoke import task

# Carpeta del proyecto: las tareas solo leen y escriben archivos dentro de ella.
ROOT = Path(__file__).resolve().parent

# Variables sin valor por defecto: se generan al azar al crear el .env.
GENERATED_SECRETS = ("JWT_SECRET", "LIBRARIAN_PASSWORD", "ADMIN_PASSWORD", "POSTGRES_PASSWORD")
VARIABLE_NAME = re.compile(r"[A-Z][A-Z0-9_]*")


def project_file(name: str) -> Path:
    """Ruta de un archivo de la raíz del proyecto.

    Se resuelve la ruta (incluidos los enlaces simbólicos) y se rechaza si apunta fuera
    de la carpeta del proyecto, para no leer ni escribir archivos ajenos.
    """
    path = (ROOT / name).resolve()
    if path.parent != ROOT:
        raise ValueError(f"{name} debe estar en la carpeta del proyecto ({ROOT})")
    return path


def parse_env(text: str) -> dict[str, str]:
    """Variables de un archivo .env; las líneas en blanco y los comentarios se ignoran."""
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep or not VARIABLE_NAME.fullmatch(name):
            raise ValueError(f"Línea inválida en el archivo de entorno: {line!r}")
        values[name] = value
    return values


def database_url(values: dict[str, str]) -> str:
    """URL de Postgres para conectarse desde la máquina al contenedor de docker-compose."""
    user = quote(values["POSTGRES_USER"], safe="")
    password = quote(values["POSTGRES_PASSWORD"], safe="")
    port = values.get("DB_PORT", "15432")
    return f"postgresql+psycopg://{user}:{password}@localhost:{port}/{values['POSTGRES_DB']}"


def missing_value(name: str, default: str, current: dict[str, str]) -> str:
    """Valor para una variable de .env.example que todavía no está en el .env."""
    if name == "POSTGRES_PASSWORD" and current.get("DATABASE_URL"):
        # Un .env anterior ya usa un volumen de Postgres creado con la clave de su URL.
        password = urlsplit(current["DATABASE_URL"]).password
        if password:
            return unquote(password)
    if default:
        return default
    if name in GENERATED_SECRETS:
        return secrets.token_urlsafe(32)
    if name == "DATABASE_URL":
        return database_url(current)
    return default


@task
def env(c):
    """Crea o completa el .env a partir de .env.example, con secretos aleatorios.

    Nunca cambia un valor que ya esté en el .env: solo agrega las variables que faltan.
    """
    target = project_file(".env")
    template = project_file(".env.example").read_text(encoding="utf-8")
    parse_env(template)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    current = parse_env(existing)

    lines = []
    for line in template.splitlines():
        name, sep, default = line.partition("=")
        if not sep or line.startswith("#"):
            if not existing:
                lines.append(line)
            continue
        if name in current:
            continue
        current[name] = missing_value(name, default, current)
        lines.append(f"{name}={current[name]}")

    if not existing:
        # "x": falla si el archivo apareció entre la comprobación y la escritura.
        with target.open("x", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")
        print(".env creado; las claves de las cuentas iniciales están ahí")
    elif lines:
        target.write_text(existing.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
        added = ", ".join(line.partition("=")[0] for line in lines)
        print(f".env completado con: {added}")






@task()
def migrate(c):
    """Aplica las migraciones pendientes."""
    c.run("alembic upgrade head")


@task()
def seed(c):
    """Crea el administrador y el bibliotecario iniciales si no existen."""
    c.run("python -m biblioteca.seed")


@task(pre=[seed])
def up(c):
    """Levanta toda la aplicación: base de datos y servidor HTTP."""
    c.run("docker-compose up --build -d")



@task
def test(c):
    """Ejecuta todas las pruebas y exige la cobertura mínima de pyproject.toml (80 %)."""
    c.run("pytest --cov")


@task
def lint(c):
    """Revisa el estilo y el formato del código con ruff."""
    c.run("ruff check --fix .")

@task
def down(c):
    """Detiene los contenedores."""
    c.run("docker compose down")
