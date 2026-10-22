from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from biblioteca.application.errors import (
    ApplicationError,
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidInputError,
    InvalidTokenError,
    NotFoundError,
)

STATUS_BY_ERROR: dict[type[ApplicationError], int] = {
    NotFoundError: 404,
    InvalidInputError: 422,
    ConflictError: 409,
    BusinessRuleError: 409,
    InvalidCredentialsError: 401,
    InvalidTokenError: 401,
    ForbiddenError: 403,
}


def _status_for(error: ApplicationError) -> int:
    for error_type, status in STATUS_BY_ERROR.items():
        if isinstance(error, error_type):
            return status
    return 400


async def _handle(request: Request, error: ApplicationError) -> JSONResponse:
    status = _status_for(error)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse({"detail": str(error)}, status_code=status, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, _handle)
