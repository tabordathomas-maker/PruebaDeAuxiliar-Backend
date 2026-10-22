from fastapi import Depends, FastAPI

from biblioteca.adapters.http import auth, health
from biblioteca.adapters.http.errors import register_error_handlers
from biblioteca.adapters.http.security import global_validator


def create_app() -> FastAPI:
    app = FastAPI(title="Biblioteca", dependencies=[Depends(global_validator)])
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
