from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from biblioteca.adapters.http.dependencies import get_uow
from biblioteca.adapters.http.schemas import LoanResponse
from biblioteca.adapters.http.security import current_principal, roles
from biblioteca.application.loans import (
    ApproveLoan,
    BorrowBook,
    CloseLoan,
    ListLoans,
    MarkLoanOverdue,
    ReturnBook,
)
from biblioteca.config import Settings, get_settings
from biblioteca.domain.entities import LoanStatus, Principal, RoleName
from biblioteca.domain.ports import UnitOfWork

router = APIRouter(prefix="/loans", tags=["loans"])


class BorrowRequest(BaseModel):
    book_id: UUID


@router.get("", response_model=list[LoanResponse])
@roles(RoleName.LIBRARIAN)
def list_all_loans(
    status: LoanStatus | None = None,
    user_id: UUID | None = None,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return [LoanResponse.of(l) for l in ListLoans(uow).execute(principal, status, user_id)]


@router.get("/me", response_model=list[LoanResponse])
@roles(RoleName.USER)
def list_my_loans(
    status: LoanStatus | None = None,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return [LoanResponse.of(l) for l in ListLoans(uow).execute(principal, status)]


@router.post("", status_code=201, response_model=LoanResponse)
@roles(RoleName.USER)
def borrow_book(
    body: BorrowRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return LoanResponse.of(BorrowBook(uow).execute(principal.user_id, body.book_id))


@router.post("/{loan_id}/return", response_model=LoanResponse)
@roles(RoleName.USER)
def return_book(
    loan_id: UUID,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return LoanResponse.of(ReturnBook(uow).execute(principal.user_id, loan_id))


@router.post("/{loan_id}/approve", response_model=LoanResponse)
@roles(RoleName.LIBRARIAN)
def approve_loan(
    loan_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
    settings: Settings = Depends(get_settings),
):
    return LoanResponse.of(ApproveLoan(uow, settings.loan_days).execute(loan_id))


@router.post("/{loan_id}/close", response_model=LoanResponse)
@roles(RoleName.LIBRARIAN)
def close_loan(loan_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return LoanResponse.of(CloseLoan(uow).execute(loan_id))


@router.post("/{loan_id}/overdue", response_model=LoanResponse)
@roles(RoleName.LIBRARIAN)
def mark_loan_overdue(loan_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return LoanResponse.of(MarkLoanOverdue(uow).execute(loan_id))
