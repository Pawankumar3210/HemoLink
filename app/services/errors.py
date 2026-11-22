"""Exception type raised by service functions for expected business-rule failures."""


class ServiceError(Exception):
    """A user-facing failure (duplicate, not allowed, wrong state, ...)."""

    def __init__(self, message, field=None, status=400):
        super().__init__(message)
        self.message = message
        self.field = field
        self.status = status
