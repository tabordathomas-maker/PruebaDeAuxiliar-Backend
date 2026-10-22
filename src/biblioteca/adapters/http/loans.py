from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from biblioteca.adapters.http.dependencies import get_uow
from biblioteca.adapters.http.schemas import LoanModificationResponse, LoanResponse
from biblioteca.adapters.http.security import current_principal, roles
from biblioteca.application.loans import (
    ApproveLoan,
    BorrowBook,
    CloseLoan,
    ListLoanModifications,
    ListLoans,
    MarkLoanOverdue,
    ModifyLoanTerms,
    ReturnBook,
)
from biblioteca.config import Settings, get_settings
from biblioteca.domain.entities import LoanStatus, Principal, RoleName
from biblioteca.domain.ports import UnitOfWork

router = APIRouter(prefix="/loans", tags=["loans"])


class BorrowRequest(BaseModel):
    book_id: UUID


class ModifyLoanRequest(BaseModel):
    """Fechas con zona horaria (ISO 8601). `due_at` y `duration_days` se excluyen."""

    model_config = ConfigDict(extra="forbid")

    loaned_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    duration_days: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _consistent(self) -> "ModifyLoanRequest":
        if self.loaned_at is None and self.due_at is None and self.duration_days is None:
            raise ValueError("Indica loaned_at, due_at o duration_days")
        if self.due_at is not None and self.duration_days is not None:
            raise ValueError("Indica due_at o duration_days, no ambos")
        return self


@router.get("", response_model=list[LoanResponse])
@roles(RoleName.LIBRARIAN)
def list_all_loans(
    status: LoanStatus | None = None,
    user_id: UUID | None = None,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return [LoanResponse.of(loan) for loan in ListLoans(uow).execute(principal, status, user_id)]


@router.get("/me", response_model=list[LoanResponse])
@roles(RoleName.USER)
def list_my_loans(
    status: LoanStatus | None = None,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    return [LoanResponse.of(loan) for loan in ListLoans(uow).execute(principal, status)]


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


@router.patch("/{loan_id}", response_model=LoanResponse)
@roles(RoleName.ADMIN, RoleName.LIBRARIAN)
def modify_loan_terms(
    loan_id: UUID,
    body: ModifyLoanRequest,
    principal: Principal = Depends(current_principal),
    uow: UnitOfWork = Depends(get_uow),
):
    loan = ModifyLoanTerms(uow).execute(
        principal.user_id,
        loan_id,
        loaned_at=body.loaned_at,
        due_at=body.due_at,
        duration_days=body.duration_days,
        reason=body.reason,
    )
    return LoanResponse.of(loan)


@router.get("/{loan_id}/modifications", response_model=list[LoanModificationResponse])
@roles(RoleName.ADMIN, RoleName.LIBRARIAN)
def list_loan_modifications(loan_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return [LoanModificationResponse.of(m) for m in ListLoanModifications(uow).execute(loan_id)]
