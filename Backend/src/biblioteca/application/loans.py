"""Casos de uso de préstamos.

Ciclo de vida: PENDING -> ACTIVE -> RETURNED, con ACTIVE -> OVERDUE -> RETURNED y
PENDING -> REJECTED. El ejemplar se reserva al solicitar y se repone al rechazar
o devolver.
"""

from uuid import UUID

from biblioteca.application.errors import BusinessRuleError, NotFoundError
from biblioteca.domain.entities import Loan, LoanStatus
from biblioteca.domain.ports import UnitOfWork

# Préstamos que todavía retienen un ejemplar.
OPEN_STATUSES = (LoanStatus.PENDING, LoanStatus.ACTIVE, LoanStatus.OVERDUE)


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
