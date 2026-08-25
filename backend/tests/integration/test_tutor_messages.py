"""Integration test: `POST /api/tutor/sessions/{id}/messages` -- the
streamed-grounded case, the honest-non-grounded case, the `409`/`429`/
`422`/`503` rejection paths, and a session recovering after a
`failed_at` exchange (`/speckit-analyze` finding H2), T017.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession
from tests.integration.tutor_helpers import (
    make_passage,
    parse_sse_events,
    patch_grounded_stream,
    patch_interrupted_stream,
    patch_moderation,
    patch_search_passages,
    patch_unavailable_stream,
    patch_unexpected_exception_stream,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def session_id(client, demo_learner, biology_subject):
    response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": str(demo_learner.learner_id), "subject_id": biology_subject.subject_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def test_streamed_grounded_answer_is_persisted(client, db_session, session_id):
    passage = make_passage(topic_id="photosynthesis", text="Light drives photosynthesis.")
    with (
        patch_moderation(allowed=True),
        patch_search_passages([passage]),
        patch_grounded_stream(
            ["Light ", "provides the energy."], grounded_passage_ids=[passage.passage_id]
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "why does photosynthesis need light?"},
        )

    assert response.status_code == 200, response.text
    events = parse_sse_events(response.text)
    deltas = [e["delta"] for e in events if "delta" in e]
    assert deltas == ["Light ", "provides the energy."]

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert events[-1] == {"done": True, "exchange_id": str(exchange.exchange_id)}
    assert exchange.answer_text == "Light provides the energy."
    assert exchange.grounded is True
    assert exchange.retrieved_passage_ids == [passage.passage_id]
    assert exchange.failed_at is None


def test_honest_non_grounded_answer_is_persisted(client, db_session, session_id):
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(
            ["I don't have material on that in this course yet."], grounded_passage_ids=[]
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "what's the capital of France?"},
        )

    assert response.status_code == 200, response.text
    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.grounded is False
    assert exchange.retrieved_passage_ids == []


def test_409_still_answering_while_a_prior_exchange_is_in_flight(client, db_session, session_id):
    db_session.add(TutorExchange(session_id=session_id, question_text="already in flight"))
    db_session.commit()

    response = client.post(
        f"/api/tutor/sessions/{session_id}/messages", json={"question": "a new question"}
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error"] == "still_answering"
    assert "exchange_id" in body


def test_429_rate_limited(client, db_session, session_id, monkeypatch):
    from src.services.tutor import rate_limit as rate_limit_module

    # A lower positive limit, not zero -- check_tutor_rate_limit derives
    # retry_after_seconds from the *oldest counted row*, so "already at
    # the limit" must be simulated with a real prior row, the same way
    # it happens in production (mirrors grading_client's check exactly,
    # research.md §8), not an empty-rows edge case that never occurs
    # with the real constant.
    monkeypatch.setattr(rate_limit_module, "RATE_LIMIT_MAX_SUBMISSIONS", 1)
    db_session.add(
        TutorExchange(session_id=session_id, question_text="prior", answer_text="answered")
    )
    db_session.commit()

    with patch_moderation(allowed=True), patch_search_passages([]):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "one question"}
        )
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["error"] == "rate_limited"
    assert body["retry_after_seconds"] >= 0


def test_422_question_too_long(client, session_id):
    from src.services.tutor.session import MAX_QUESTION_LENGTH

    response = client.post(
        f"/api/tutor/sessions/{session_id}/messages",
        json={"question": "a" * (MAX_QUESTION_LENGTH + 1)},
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"error": "question_too_long", "max_length": MAX_QUESTION_LENGTH}


def test_422_moderation_rejected(client, session_id):
    with patch_moderation(allowed=False):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "abusive content"}
        )
    assert response.status_code == 422, response.text
    assert response.json() == {"error": "moderation_rejected"}


def test_503_tutor_unavailable_marks_exchange_failed_not_stuck(client, db_session, session_id):
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_unavailable_stream(),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "a question"}
        )
    assert response.status_code == 503, response.text
    assert response.json() == {"error": "tutor_unavailable"}

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.answer_text is None
    assert exchange.failed_at is not None

    # The session is NOT stuck behind a phantom in-flight exchange
    # (finding H2) -- a fresh question on the same session succeeds.
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["all good now"], grounded_passage_ids=[]),
    ):
        retry = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "try again"}
        )
    assert retry.status_code == 200, retry.text


def test_session_recovers_after_a_mid_stream_failure(client, db_session, session_id):
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_interrupted_stream(["partial answer before it broke"]),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "a question"}
        )
    # No 5xx surfaced to the caller -- contracts/api.md: "no
    # learner-facing response for this case beyond the connection
    # simply ending".
    assert response.status_code == 200, response.text

    exchanges = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).all()
    assert len(exchanges) == 1
    assert exchanges[0].answer_text is None
    assert exchanges[0].failed_at is not None

    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["recovered answer"], grounded_passage_ids=[]),
    ):
        retry = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "try again"}
        )
    assert retry.status_code == 200, retry.text

    remaining = (
        db_session.query(TutoringSession).filter(TutoringSession.session_id == session_id).one()
    )
    assert remaining.status.value == "active"


def test_session_recovers_after_an_unexpected_exception_mid_stream(client, db_session, session_id):
    """PR #32 review finding: `stream_message_response` previously only
    caught `TutorStreamInterruptedError` -- any other exception left
    the exchange permanently stuck `answer_text IS NULL AND failed_at
    IS NULL`, reproducing finding H2's deadlock for an untested failure
    mode."""
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_unexpected_exception_stream(["partial answer before the bug"]),
    ):
        with pytest.raises(ValueError, match="simulated unexpected bug"):
            client.post(
                f"/api/tutor/sessions/{session_id}/messages", json={"question": "a question"}
            )

    exchanges = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).all()
    assert len(exchanges) == 1
    assert exchanges[0].answer_text is None
    assert exchanges[0].failed_at is not None

    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["recovered answer"], grounded_passage_ids=[]),
    ):
        retry = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "try again"}
        )
    assert retry.status_code == 200, retry.text
