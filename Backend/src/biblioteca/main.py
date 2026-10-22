from fastapi import FastAPI

from biblioteca.adapters.http import auth, health
from biblioteca.adapters.http.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="Biblioteca")
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
