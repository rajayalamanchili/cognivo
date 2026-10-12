"""Raw outbound-email call (spec 045 research.md §1/§7) -- a single
`httpx.post()` to Resend's REST API, no SDK dependency. Never raises:
any exception or non-2xx response is caught and treated as a failure,
since a failed send must never block the action that triggered it
(FR-012)."""

import os

import httpx

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 10.0


def send_email(to_email: str, subject: str, body: str) -> bool:
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
        return response.is_success
    except httpx.HTTPError:
        return False
