import pytest

from biblioteca.domain.ports import BookRepository, LoanRepository, UnitOfWork


@pytest.mark.parametrize("port", [BookRepository, LoanRepository, UnitOfWork])
def test_ports_are_abstract(port):
    with pytest.raises(TypeError):
        port()


def test_unit_of_work_rolls_back_on_exit(mocker):
    uow = mocker.Mock(spec=UnitOfWork)

    UnitOfWork.__exit__(uow, None, None, None)

    uow.rollback.assert_called_once_with()
