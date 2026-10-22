"""Casos de uso de préstamos.

Ciclo de vida: PENDING -> ACTIVE -> RETURNED, con ACTIVE -> OVERDUE -> RETURNED y
PENDING -> REJECTED. El ejemplar se reserva al solicitar y se repone al rechazar
o devolver.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from biblioteca.application.errors import BusinessRuleError, ForbiddenError, NotFoundError
from biblioteca.domain.entities import Loan, LoanStatus, Principal, RoleName
from biblioteca.domain.ports import UnitOfWork

# Préstamos que todavía retienen un ejemplar.
OPEN_STATUSES = (LoanStatus.PENDING, LoanStatus.ACTIVE, LoanStatus.OVERDUE)
# Préstamos con el libro en manos del usuario.
LOANED_STATUSES = (LoanStatus.ACTIVE, LoanStatus.OVERDUE)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _restore_copy(uow: UnitOfWork, book_id: UUID) -> None:
    book = uow.books.get(book_id, for_update=True)
    book.available_copies += 1
    uow.books.update(book)


def _register_return(uow: UnitOfWork, loan: Loan, now: datetime) -> None:
    if loan.status not in LOANED_STATUSES:
        raise BusinessRuleError(f"Un préstamo en estado {loan.status} no se puede devolver")
    loan.status = LoanStatus.RETURNED
    loan.returned_at = now
    uow.loans.update(loan)
    _restore_copy(uow, loan.book_id)


class BorrowBook:
    """El usuario solicita un libro: queda pendiente de aprobación con un ejemplar reservado."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, user_id: UUID, book_id: UUID) -> Loan:
        with self.uow:
            # Bloquear el libro evita que dos solicitudes simultáneas se lleven la última copia.
            book = self.uow.books.get(book_id, for_update=True)
            if book is None:
                raise NotFoundError("El libro no existe")
            if self.uow.loans.list(user_id=user_id, book_id=book_id, statuses=OPEN_STATUSES):
                raise BusinessRuleError("Ya tienes un préstamo abierto de este libro")
            if book.available_copies < 1:
                raise BusinessRuleError("No hay ejemplares disponibles de este libro")

            book.available_copies -= 1
            self.uow.books.update(book)
            loan = Loan(user_id=user_id, book_id=book_id)
            self.uow.loans.add(loan)
            self.uow.commit()
            return loan


class ReturnBook:
    """El usuario devuelve un libro que tiene prestado (activo o vencido)."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self.uow = uow
        self.clock = clock

    def execute(self, user_id: UUID, loan_id: UUID) -> Loan:
        with self.uow:
            loan = self.uow.loans.get(loan_id, for_update=True)
            # Los préstamos ajenos se tratan como inexistentes para no revelarlos.
            if loan is None or loan.user_id != user_id:
                raise NotFoundError("El préstamo no existe")
            _register_return(self.uow, loan, self.clock())
            self.uow.commit()
            return loan


class ListLoans:
    """El bibliotecario ve todos los préstamos; el usuario solo los suyos."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(
        self,
        requester: Principal,
        status: LoanStatus | None = None,
        user_id: UUID | None = None,
    ) -> list[Loan]:
        if requester.role != RoleName.LIBRARIAN:
            if user_id is not None and user_id != requester.user_id:
                raise ForbiddenError("Solo puedes ver tus propios préstamos")
            user_id = requester.user_id
        statuses = [status] if status is not None else None
        with self.uow:
            return self.uow.loans.list(user_id=user_id, statuses=statuses)
