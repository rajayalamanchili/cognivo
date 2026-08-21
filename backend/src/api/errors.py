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


class TooLongError(DomainError):
    """Maps to HTTP 422 (spec 007 FR-015): `{"error": "answer_too_long",
    "max_length": ...}`, a distinct shape from `UnprocessableError`'s
    generic `{"detail": ...}` -- contracts/api.md's free-text rejection
    responses are structured, not free-text messages."""

    def __init__(self, max_length: int):
        super().__init__("answer_too_long")
        self.max_length = max_length


class RateLimitedError(DomainError):
    """Maps to HTTP 429 (spec 007 FR-016)."""

    def __init__(self, retry_after_seconds: int):
        super().__init__("rate_limited")
        self.retry_after_seconds = retry_after_seconds


class ModerationRejectedError(DomainError):
    """Maps to HTTP 422 (spec 007 FR-012). Deliberately carries no detail
    about which rule was tripped (contracts/api.md) -- the reason is
    still logged server-side via `free_text_submission_rejected`."""

    def __init__(self):
        super().__init__("moderation_rejected")


class GradingUnavailableError(DomainError):
    """Maps to HTTP 503 (spec 007 FR-010/FR-014) -- the Grading Agent was
    unreachable, timed out, or its response repeatedly failed rubric-shape
    validation after all retries were exhausted."""

    def __init__(self):
        super().__init__("grading_unavailable")
