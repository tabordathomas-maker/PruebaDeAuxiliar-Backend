from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from biblioteca.adapters.http.dependencies import get_uow
from biblioteca.adapters.http.schemas import LoanResponse
from biblioteca.adapters.http.security import current_principal, roles
from biblioteca.application.loans import BorrowBook
from biblioteca.domain.entities import Principal, RoleName
from biblioteca.domain.ports import UnitOfWork

router = APIRouter(prefix="/loans", tags=["loans"])


class BorrowRequest(BaseModel):
    book_id: UUID


@router.post("", status_code=201, response_model=LoanResponse)
@roles(RoleName.USER)
def borrow_book(
    body: BorrowRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return LoanResponse.of(BorrowBook(uow).execute(principal.user_id, body.book_id))
