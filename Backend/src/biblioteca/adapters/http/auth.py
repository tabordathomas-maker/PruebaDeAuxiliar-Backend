from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from biblioteca.adapters.http.dependencies import get_hasher, get_token_service, get_uow
from biblioteca.application.auth import Login, RegisterUser
from biblioteca.domain.ports import PasswordHasher, TokenService, UnitOfWork

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str


class LoginRequest(BaseModel):
    # Sin validar el formato: un email desconocido simplemente da 401.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=201, response_model=UserResponse)
def register(
    body: RegisterRequest,
    uow: UnitOfWork = Depends(get_uow),
    hasher: PasswordHasher = Depends(get_hasher),
):
    # El registro público siempre crea usuarios con rol "user".
    user = RegisterUser(uow, hasher).execute(body.name, body.email, body.password)
    return UserResponse(id=user.id, name=user.name, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    uow: UnitOfWork = Depends(get_uow),
    hasher: PasswordHasher = Depends(get_hasher),
    tokens: TokenService = Depends(get_token_service),
):
    return TokenResponse(access_token=Login(uow, hasher, tokens).execute(body.email, body.password))
