from fastapi import Depends, FastAPI

from biblioteca.adapters.http import auth, catalog, health, loans, users
from biblioteca.adapters.http.errors import register_error_handlers
from biblioteca.adapters.http.security import global_validator, label_restricted_routes
from biblioteca.config import get_settings


def create_app() -> FastAPI:
    # Sin los secretos obligatorios la app se niega a arrancar (ConfigurationError).
    get_settings()
    app = FastAPI(title="Biblioteca", dependencies=[Depends(global_validator)])
    register_error_handlers(app)
    app.include_router(label_restricted_routes(health.router))
    app.include_router(label_restricted_routes(auth.router))
    app.include_router(label_restricted_routes(catalog.router))
    app.include_router(label_restricted_routes(loans.router))
    app.include_router(label_restricted_routes(users.router))
    return app


app = create_app()
