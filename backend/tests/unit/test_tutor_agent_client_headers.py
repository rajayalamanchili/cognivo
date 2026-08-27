"""Unit test: `tutor_agent_client/client.py`'s `_build_headers()` sends
`X-Tutor-Exchange-Id`/`X-Tutor-Session-Id` on every A2A call.

Found during the T038 grounding investigation (roadmap.md): tutor-agent/'s
own Langfuse trace had no link back to this backend's `TutorExchange` row
at all -- the two could only be matched by question text + rough
timestamp, which proved unreliable enough to block root-causing a real
grounding failure. These headers carry no auth role (the shared secret
above already covers that); tutor-agent/'s `_TraceCorrelationMiddleware`
reads them back purely for trace correlation.
"""

import uuid

from src.services.tutor_agent_client.client import _build_headers


def test_headers_include_exchange_and_session_id(monkeypatch):
    monkeypatch.setenv("TUTOR_AGENT_SHARED_SECRET", "test-shared-secret")
    exchange_id = uuid.uuid4()
    session_id = uuid.uuid4()

    headers = _build_headers(exchange_id=exchange_id, session_id=session_id)

    assert headers["X-Tutor-Exchange-Id"] == str(exchange_id)
    assert headers["X-Tutor-Session-Id"] == str(session_id)
    assert headers["X-Tutor-Agent-Secret"] == "test-shared-secret"


def test_headers_omit_vercel_bypass_when_unset(monkeypatch):
    monkeypatch.setenv("TUTOR_AGENT_SHARED_SECRET", "test-shared-secret")
    monkeypatch.delenv("TUTOR_AGENT_VERCEL_BYPASS_SECRET", raising=False)

    headers = _build_headers(exchange_id=uuid.uuid4(), session_id=uuid.uuid4())

    assert "x-vercel-protection-bypass" not in headers
