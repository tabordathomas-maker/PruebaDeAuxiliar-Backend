"""Errores que lanzan los casos de uso; el adaptador HTTP los traduce a códigos."""


class ApplicationError(Exception):
    pass


class NotFoundError(ApplicationError):
    pass


class InvalidInputError(ApplicationError):
    """Un dato no es válido aunque tenga el formato correcto (por ejemplo, un texto en blanco)."""


class ConflictError(ApplicationError):
    """El recurso ya existe."""


class BusinessRuleError(ApplicationError):
    """La operación viola una regla de negocio (sin stock, transición no válida...)."""


class StockError(BusinessRuleError):
    """Las copias del libro no permiten la operación."""


class InvalidCredentialsError(ApplicationError):
    pass


class InvalidTokenError(ApplicationError):
    pass


class ForbiddenError(ApplicationError):
    """El usuario está autenticado pero no puede actuar sobre ese recurso."""


def required_text(value: str, label: str) -> str:
    """Quita los espacios de los extremos y rechaza el texto que queda vacío."""
    text = value.strip()
    if not text:
        raise InvalidInputError(f"{label} no puede estar en blanco")
    return text
