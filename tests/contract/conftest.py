"""Corre el mismo contrato contra cada implementación de repositorio.

Que ambas variantes pasen las mismas pruebas demuestra que son intercambiables.
"""

import pytest


@pytest.fixture(params=["memory", "postgres"])
def uow(request):
    return request.getfixturevalue(f"{request.param}_uow")
