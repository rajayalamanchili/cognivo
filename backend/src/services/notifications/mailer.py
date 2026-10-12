"""Raw outbound-email call (spec 045 research.md §1/§7) -- a single
`httpx.post()` to Resend's REST API, no SDK dependency. Never raises:
any exception or non-2xx response is caught and treated as a failure,
since a failed send must never block the action that triggered it
(FR-012)."""

import os

import httpx

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 10.0
# PR #115 review finding: `error_detail` carries this verbatim --
# truncate so a verbose provider error body can't bloat the log row.
_FAILURE_DETAIL_MAX_LENGTH = 200


def send_email(to_email: str, subject: str, body: str) -> tuple[bool, str | None]:
    """Returns `(success, failure_detail)` -- `failure_detail` is
    `None` on success, else a short, non-secret description (the
    provider's status code + response body, or the caught exception's
    type/message) for `NotificationLogEntry.error_detail` (PR #115
    review finding: a prior bare `bool` return discarded this)."""
    try:
        response = httpx.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {os.environ.get('RESEND_API_KEY', '')}"},
            json={
                "from": os.environ.get("EMAIL_FROM_ADDRESS", ""),
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        if response.is_success:
            return True, None
        detail = f"HTTP {response.status_code}: {response.text}"
        return False, detail[:_FAILURE_DETAIL_MAX_LENGTH]
    except httpx.HTTPError as exc:
        detail = f"{type(exc).__name__}: {exc}"
        return False, detail[:_FAILURE_DETAIL_MAX_LENGTH]
