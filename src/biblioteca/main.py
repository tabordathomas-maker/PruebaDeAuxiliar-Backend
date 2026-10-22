from fastapi import Depends, FastAPI

from biblioteca.adapters.http import auth, catalog, health, loans, users
from biblioteca.adapters.http.errors import register_error_handlers
from biblioteca.adapters.http.security import global_validator
from biblioteca.config import get_settings


def create_app() -> FastAPI:
    # Sin los secretos obligatorios la app se niega a arrancar (ConfigurationError).
    get_settings()
    app = FastAPI(title="Biblioteca", dependencies=[Depends(global_validator)])
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(loans.router)
    app.include_router(users.router)
    return app


app = create_app()
