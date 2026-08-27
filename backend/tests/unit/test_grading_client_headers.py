"""Unit test: `grading_client/client.py`'s `_build_headers()` sends
`X-Grading-Question-Id`/`X-Grading-Learner-Id` on every A2A call.

Same trace-correlation gap and fix as `tutor_agent_client/client.py`'s
copy of this test (found during the T038 grounding investigation,
roadmap.md, and applied here too since Grading Agent has the identical
A2A-hop-with-no-correlation-header gap). These headers carry no auth
role (the shared secret above already covers that); grading-agent/'s
`_TraceCorrelationMiddleware` reads them back purely for trace
correlation.
"""

import uuid

from src.services.grading_client.client import _build_headers


def test_headers_include_question_and_learner_id(monkeypatch):
    monkeypatch.setenv("GRADING_AGENT_SHARED_SECRET", "test-shared-secret")
    question_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    headers = _build_headers(question_id=question_id, learner_id=learner_id)

    assert headers["X-Grading-Question-Id"] == str(question_id)
    assert headers["X-Grading-Learner-Id"] == str(learner_id)
    assert headers["X-Grading-Agent-Secret"] == "test-shared-secret"


def test_headers_omit_vercel_bypass_when_unset(monkeypatch):
    monkeypatch.setenv("GRADING_AGENT_SHARED_SECRET", "test-shared-secret")
    monkeypatch.delenv("GRADING_AGENT_VERCEL_BYPASS_SECRET", raising=False)

    headers = _build_headers(question_id=uuid.uuid4(), learner_id=uuid.uuid4())

    assert "x-vercel-protection-bypass" not in headers
