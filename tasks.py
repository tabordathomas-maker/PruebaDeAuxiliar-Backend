from invoke import task


@task
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
    """Ejecuta todas las pruebas."""
    c.run("pytest")


@task
def down(c):
    """Detiene los contenedores."""
    c.run("docker compose down")
