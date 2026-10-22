"""Casos de uso de préstamos.

Ciclo de vida: PENDING -> ACTIVE -> RETURNED, con ACTIVE -> OVERDUE -> RETURNED y
PENDING -> REJECTED. El ejemplar se reserva al solicitar y se repone al rechazar
o devolver.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from biblioteca.application.errors import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    StockError,
)
from biblioteca.domain.entities import Loan, LoanModification, LoanStatus, Principal, RoleName
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


def _as_utc(value: datetime) -> datetime:
    """Las fechas que llegan de fuera deben traer zona horaria; se guardan en UTC."""
    if value.tzinfo is None:
        raise BusinessRuleError("Las fechas deben incluir la zona horaria")
    return value.astimezone(UTC)


def _audit_value(value: datetime | LoanStatus | None) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return None if value is None else str(value)


def _get_loan_for_update(uow: UnitOfWork, loan_id: UUID) -> Loan:
    loan = uow.loans.get(loan_id, for_update=True)
    if loan is None:
        raise NotFoundError("El préstamo no existe")
    return loan


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
                raise StockError("No hay ejemplares disponibles de este libro")

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


class ApproveLoan:
    """El bibliotecario aprueba una solicitud: el préstamo empieza a correr.

    El ejemplar ya se reservó al solicitar, pero se vuelve a validar el stock por si
    los datos dejaron de cuadrar desde entonces.
    """

    def __init__(self, uow: UnitOfWork, loan_days: int, clock: Clock = utc_now) -> None:
        self.uow = uow
        self.loan_days = loan_days
        self.clock = clock

    def execute(self, loan_id: UUID) -> Loan:
        with self.uow:
            loan = _get_loan_for_update(self.uow, loan_id)
            if loan.status is not LoanStatus.PENDING:
                raise BusinessRuleError(
                    f"Solo se aprueban préstamos pendientes, este está {loan.status}"
                )
            self._ensure_stock(loan)

            now = self.clock()
            loan.status = LoanStatus.ACTIVE
            loan.loaned_at = now
            loan.due_at = now + timedelta(days=self.loan_days)
            self.uow.loans.update(loan)
            self.uow.commit()
            return loan

    def _ensure_stock(self, loan: Loan) -> None:
        book = self.uow.books.get(loan.book_id, for_update=True)
        if book is None:
            raise StockError("El libro del préstamo ya no existe")
        # Cada préstamo abierto, incluido este, retiene un ejemplar.
        open_loans = len(self.uow.loans.list(book_id=book.id, statuses=OPEN_STATUSES))
        expected_available = book.total_copies - open_loans
        if open_loans > book.total_copies or book.available_copies != expected_available:
            raise StockError("Las copias del libro no cuadran con sus préstamos abiertos")


class CloseLoan:
    """El bibliotecario cierra un préstamo: rechaza el pendiente o registra la devolución."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self.uow = uow
        self.clock = clock

    def execute(self, loan_id: UUID) -> Loan:
        with self.uow:
            loan = _get_loan_for_update(self.uow, loan_id)
            if loan.status is LoanStatus.PENDING:
                loan.status = LoanStatus.REJECTED
                self.uow.loans.update(loan)
                _restore_copy(self.uow, loan.book_id)
            else:
                _register_return(self.uow, loan, self.clock())
            self.uow.commit()
            return loan


class MarkLoanOverdue:
    """El bibliotecario marca como vencido un préstamo activo cuya fecha límite pasó."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self.uow = uow
        self.clock = clock

    def execute(self, loan_id: UUID) -> Loan:
        with self.uow:
            loan = _get_loan_for_update(self.uow, loan_id)
            if loan.status is not LoanStatus.ACTIVE:
                raise BusinessRuleError(
                    f"Solo se marcan vencidos préstamos activos, este está {loan.status}"
                )
            if loan.due_at >= self.clock():
                raise BusinessRuleError("El préstamo todavía no ha llegado a su fecha límite")

            loan.status = LoanStatus.OVERDUE
            self.uow.loans.update(loan)
            self.uow.commit()
            return loan


class ModifyLoanTerms:
    """Administrador o bibliotecario cambian la fecha de salida, la fecha límite o la duración.

    Solo en préstamos activos o vencidos: los pendientes aún no tienen fechas y los
    cerrados ya son historia. Si un préstamo vencido recibe una fecha límite futura,
    vuelve a estar activo. El cambio y su registro de auditoría se confirman en la
    misma transacción: o se guardan los dos o ninguno.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self.uow = uow
        self.clock = clock

    def execute(
        self,
        actor_id: UUID,
        loan_id: UUID,
        loaned_at: datetime | None = None,
        due_at: datetime | None = None,
        duration_days: int | None = None,
        reason: str | None = None,
    ) -> Loan:
        if loaned_at is None and due_at is None and duration_days is None:
            raise BusinessRuleError("Indica la fecha de salida, la fecha límite o la duración")
        if due_at is not None and duration_days is not None:
            raise BusinessRuleError("Indica la fecha límite o la duración, no ambas")
        if duration_days is not None and duration_days < 1:
            raise BusinessRuleError("La duración debe ser de al menos un día")

        now = self.clock()
        with self.uow:
            loan = _get_loan_for_update(self.uow, loan_id)
            if loan.status not in LOANED_STATUSES:
                raise BusinessRuleError(
                    f"Solo se modifican los plazos de préstamos activos o vencidos, "
                    f"este está {loan.status}"
                )

            new_loaned_at = _as_utc(loaned_at) if loaned_at is not None else loan.loaned_at
            if duration_days is not None:
                new_due_at = new_loaned_at + timedelta(days=duration_days)
            elif due_at is not None:
                new_due_at = _as_utc(due_at)
            else:
                new_due_at = loan.due_at
            if new_loaned_at > now:
                raise BusinessRuleError("La fecha de salida no puede estar en el futuro")
            if new_due_at <= new_loaned_at:
                raise BusinessRuleError("La fecha límite debe ser posterior a la de salida")
            new_status = loan.status
            if loan.status is LoanStatus.OVERDUE and new_due_at > now:
                new_status = LoanStatus.ACTIVE

            before = {"loaned_at": loan.loaned_at, "due_at": loan.due_at, "status": loan.status}
            after = {"loaned_at": new_loaned_at, "due_at": new_due_at, "status": new_status}
            changed = [name for name in before if before[name] != after[name]]
            if not changed:
                raise BusinessRuleError("Los plazos indicados son iguales a los actuales")

            loan.loaned_at, loan.due_at, loan.status = new_loaned_at, new_due_at, new_status
            self.uow.loans.update(loan)
            self.uow.loan_modifications.add(
                LoanModification(
                    loan_id=loan.id,
                    modified_by=actor_id,
                    modified_at=now,
                    changed_fields=changed,
                    old_values={name: _audit_value(before[name]) for name in changed},
                    new_values={name: _audit_value(after[name]) for name in changed},
                    reason=(reason or "").strip() or None,
                )
            )
            self.uow.commit()
            return loan


class ListLoanModifications:
    """Historial de cambios de un préstamo, del más antiguo al más reciente."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, loan_id: UUID) -> list[LoanModification]:
        with self.uow:
            if self.uow.loans.get(loan_id) is None:
                raise NotFoundError("El préstamo no existe")
            return self.uow.loan_modifications.list_by_loan(loan_id)
