from fastapi import FastAPI

from biblioteca.adapters.http import health


def create_app() -> FastAPI:
    app = FastAPI(title="Biblioteca")
    app.include_router(health.router)
    return app


app = create_app()
