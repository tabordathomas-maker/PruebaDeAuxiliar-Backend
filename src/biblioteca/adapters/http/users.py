from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from biblioteca.adapters.http.dependencies import get_hasher, get_uow
from biblioteca.adapters.http.schemas import UserProfileResponse
from biblioteca.adapters.http.security import current_principal, roles
from biblioteca.application.users import (
    CreateAccount,
    DeactivateAccount,
    GetAccount,
    ListAccounts,
    UpdateAccount,
)
from biblioteca.domain.entities import Principal, RoleName
from biblioteca.domain.ports import PasswordHasher, UnitOfWork

router = APIRouter(prefix="/users", tags=["users"])


class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal[RoleName.LIBRARIAN, RoleName.USER]


class UpdateAccountRequest(BaseModel):
    # extra="forbid": mandar `role`, `active` o `id` responde 422 en vez de ignorarse.
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)

    @model_validator(mode="after")
    def _not_empty(self) -> "UpdateAccountRequest":
        if self.name is None and self.email is None and self.password is None:
            raise ValueError("Indica al menos un dato que modificar")
        return self


def _update(
    principal: Principal, user_id: UUID, body: UpdateAccountRequest, uow, hasher
) -> UserProfileResponse:
    profile = UpdateAccount(uow, hasher).execute(
        principal, user_id, body.name, body.email, body.password
    )
    return UserProfileResponse.of(profile)


# Las rutas /me van antes que /{user_id} para que "me" no se lea como un id.


@router.get("/me", response_model=UserProfileResponse)
def get_my_account(
    principal: Principal = Depends(current_principal), uow: UnitOfWork = Depends(get_uow)
):
    return UserProfileResponse.of(GetAccount(uow).execute(principal, principal.user_id))


@router.put("/me", response_model=UserProfileResponse)
@roles(RoleName.USER)
def update_my_account(
    body: UpdateAccountRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
    hasher: PasswordHasher = Depends(get_hasher),
):
    return _update(principal, principal.user_id, body, uow, hasher)


@router.delete("/me", status_code=204)
@roles(RoleName.USER)
def deactivate_my_account(
    principal: Principal = Depends(current_principal), uow: UnitOfWork = Depends(get_uow)
):
    DeactivateAccount(uow).execute(principal, principal.user_id)
    return Response(status_code=204)


@router.post("", status_code=201, response_model=UserProfileResponse)
@roles(RoleName.ADMIN)
def create_account(
    body: CreateAccountRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
    hasher: PasswordHasher = Depends(get_hasher),
):
    profile = CreateAccount(uow, hasher).execute(
        principal, body.name, body.email, body.password, body.role
    )
    return UserProfileResponse.of(profile)


@router.get("", response_model=list[UserProfileResponse])
@roles(RoleName.ADMIN)
def list_accounts(
    role: Literal[RoleName.LIBRARIAN, RoleName.USER] | None = None,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return [UserProfileResponse.of(p) for p in ListAccounts(uow).execute(principal, role)]


@router.get("/{user_id}", response_model=UserProfileResponse)
@roles(RoleName.ADMIN)
def get_account(
    user_id: UUID,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return UserProfileResponse.of(GetAccount(uow).execute(principal, user_id))


@router.put("/{user_id}", response_model=UserProfileResponse)
@roles(RoleName.ADMIN)
def update_account(
    user_id: UUID,
    body: UpdateAccountRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
    hasher: PasswordHasher = Depends(get_hasher),
):
    return _update(principal, user_id, body, uow, hasher)


@router.delete("/{user_id}", status_code=204)
@roles(RoleName.ADMIN, RoleName.LIBRARIAN)
def deactivate_account(
    user_id: UUID,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    DeactivateAccount(uow).execute(principal, user_id)
    return Response(status_code=204)
