"""Dos usuarios piden a la vez la última copia: con Postgres solo uno puede llevársela."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from biblioteca.adapters.persistence.postgres.repositories import PostgresUnitOfWork
from biblioteca.application.auth import RegisterUser
from biblioteca.application.catalog import CreateBook
from biblioteca.application.errors import BusinessRuleError
from biblioteca.application.loans import BorrowBook


def test_last_copy_goes_to_a_single_request(postgres_uow, hasher):
    book = CreateBook(postgres_uow).execute("Rayuela", "Cortázar", "978-1", 1)
    users = [
        RegisterUser(postgres_uow, hasher).execute(f"U{i}", f"u{i}@example.com", "secreto123")
        for i in range(2)
    ]
    start = Barrier(len(users))

    def borrow(user_id):
        start.wait()
        try:
            # Cada hilo con su propia unidad de trabajo, como dos peticiones HTTP.
            uow = PostgresUnitOfWork(postgres_uow.session_factory)
            BorrowBook(uow).execute(user_id, book.id)
            return "ok"
        except BusinessRuleError:
            return "sin stock"

    with ThreadPoolExecutor(len(users)) as pool:
        results = sorted(pool.map(borrow, [u.id for u in users]))

    assert results == ["ok", "sin stock"]
    with postgres_uow:
        assert postgres_uow.books.get(book.id).available_copies == 0
        assert len(postgres_uow.loans.list(book_id=book.id)) == 1
