"""Raw outbound-email call (spec 045 research.md §1/§7) -- a single
`httpx.post()` to Resend's REST API, no SDK dependency. Never raises:
any exception or non-2xx response is caught and treated as a failure,
since a failed send must never block the action that triggered it
(FR-012)."""

import os
import re

import httpx

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 10.0
# `error_detail` carries this verbatim -- truncate so a verbose
# provider error body can't bloat the log row.
_FAILURE_DETAIL_MAX_LENGTH = 200


def _redact(detail: str, to_email: str) -> str:
    """A provider error body can echo the recipient address back
    verbatim (e.g. an "invalid `to` address ..." message) -- that
    would write PII into `notification_log_entries`, a table outside
    the account/retention path (Principle VIII), via a raw string this
    function never otherwise inspects. Scrubbed defensively on every
    failure path, not just the HTTP one, since an exception's own
    message can also happen to contain it.

    Case-insensitive (review finding: providers can echo the address
    normalized/lowercased) and guarded against an empty `to_email` --
    an exact-match `str.replace("", ...)` would otherwise insert the
    placeholder between every character of `detail`."""
    if not to_email:
        return detail
    return re.sub(re.escape(to_email), "[recipient email redacted]", detail, flags=re.IGNORECASE)


def send_email(to_email: str, subject: str, body: str) -> tuple[bool, str | None]:
    """Returns `(success, failure_detail)` -- `failure_detail` is
    `None` on success, else a short, non-secret description (the
    provider's status code + response body, or the caught exception's
    type/message) for `NotificationLogEntry.error_detail`."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_address = os.environ.get("EMAIL_FROM_ADDRESS", "")
    if not api_key or not from_address:
        return False, "RESEND_API_KEY/EMAIL_FROM_ADDRESS not configured"
    try:
        response = httpx.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        if response.is_success:
            return True, None
        detail = _redact(f"HTTP {response.status_code}: {response.text}", to_email)
        return False, detail[:_FAILURE_DETAIL_MAX_LENGTH]
    except Exception as exc:  # noqa: BLE001 -- never raises (FR-012)
        detail = _redact(f"{type(exc).__name__}: {exc}", to_email)
        return False, detail[:_FAILURE_DETAIL_MAX_LENGTH]
