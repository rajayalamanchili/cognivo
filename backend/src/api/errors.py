"""Domain error types shared by every route module.

Routes raise these instead of constructing `HTTPException` directly, so
the status-code mapping required by contracts/api.md (404/409/422 per
endpoint) lives in exactly one place (`main.py`'s exception handlers).
"""


class DomainError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """Maps to HTTP 404."""


class ConflictError(DomainError):
    """Maps to HTTP 409."""


class UnprocessableError(DomainError):
    """Maps to HTTP 422."""
