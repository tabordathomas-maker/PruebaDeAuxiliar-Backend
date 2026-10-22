import secrets
from pathlib import Path

from invoke import task

# Variables sin valor por defecto en config.py: se generan al azar al crear el .env.
GENERATED_SECRETS = ("JWT_SECRET", "LIBRARIAN_PASSWORD", "ADMIN_PASSWORD")


@task
def env(c):
    """Crea el .env a partir de .env.example con secretos aleatorios, si no existe."""
    target = Path(".env")
    if target.exists():
        return
    lines = []
    for line in Path(".env.example").read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name in GENERATED_SECRETS and not value:
            line = f"{name}={secrets.token_urlsafe(32)}"
        lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(".env creado; las claves de las cuentas iniciales están ahí")


@task(pre=[env])
def db(c):
    """Levanta Postgres y espera a que acepte conexiones."""
    c.run("docker compose up -d --wait db")


@task(pre=[db])
def migrate(c):
    """Aplica las migraciones pendientes."""
    c.run("alembic upgrade head")


@task(pre=[migrate])
def seed(c):
    """Crea el administrador y el bibliotecario iniciales si no existen."""
    c.run("python -m biblioteca.seed")


@task(pre=[seed])
def up(c, host="127.0.0.1", port=8000):
    """Levanta toda la aplicación: base de datos y servidor HTTP."""
    c.run(f"uvicorn biblioteca.main:app --app-dir src --host {host} --port {port}")


@task
def test(c):
    """Ejecuta todas las pruebas y exige la cobertura mínima de pyproject.toml (80 %)."""
    c.run("pytest --cov")


@task
def lint(c):
    """Revisa el estilo y el formato del código con ruff."""
    c.run("ruff check .")
    c.run("ruff format --check .")


@task
def down(c):
    """Detiene los contenedores."""
    c.run("docker compose down")
