"""Errores que lanzan los casos de uso; el adaptador HTTP los traduce a códigos."""


class ApplicationError(Exception):
    pass


class NotFoundError(ApplicationError):
    pass


class ConflictError(ApplicationError):
    """El recurso ya existe."""


class BusinessRuleError(ApplicationError):
    """La operación viola una regla de negocio (sin stock, transición no válida...)."""


class InvalidCredentialsError(ApplicationError):
    pass


class InvalidTokenError(ApplicationError):
    pass


class ForbiddenError(ApplicationError):
    """El usuario está autenticado pero no puede actuar sobre ese recurso."""
