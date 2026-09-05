"""Integration test: `POST /api/tutor/sessions/{id}/messages` -- the
streamed-grounded case, the honest-non-grounded case, the `409`/`429`/
`422`/`503` rejection paths, and a session recovering after a
`failed_at` exchange (`/speckit-analyze` finding H2), T017.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import asyncio
import uuid

import pytest

from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession
from src.services.tutor.session import prepare_message
from tests.integration.tutor_helpers import (
    make_passage,
    parse_sse_events,
    patch_disconnected_stream,
    patch_grounded_stream,
    patch_grounded_stream_capturing,
    patch_interrupted_stream,
    patch_moderation,
    patch_search_passages,
    patch_search_passages_failure,
    patch_shielding_match,
    patch_shielding_match_failure,
    patch_unavailable_stream,
    patch_unexpected_exception_opening_stream,
    patch_unexpected_exception_stream,
    seed_open_question,
    seed_open_quiz_assignment_question,
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


def test_direct_ask_against_an_open_question_is_shielded(
    client, db_session, session_id, demo_learner, biology_subject
):
    """spec 016 US1/SC-001: a tutor question directly asking for the
    answer to a currently-open, unanswered question gets a hint-only
    response, and the exchange records which question triggered it."""
    open_question = seed_open_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    captured: dict = {}
    with (
        patch_moderation(allowed=True),
        patch_shielding_match(matches=True),
        patch_search_passages([]),
        patch_grounded_stream_capturing(
            ["Think about what you already know first."],
            grounded_passage_ids=[],
            captured_kwargs=captured,
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "just give me the answer to that question"},
        )

    assert response.status_code == 200, response.text
    assert captured["shielding"] == {
        "open_question_stem": open_question.stem,
        "open_question_topic_id": open_question.topic_id,
    }

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.shielded is True
    assert exchange.shielded_question_id == open_question.question_id


def test_unrelated_question_is_not_shielded_while_a_question_is_open(
    client, db_session, session_id, demo_learner, biology_subject
):
    """spec 016 US2/SC-002: an open, unanswered question elsewhere in
    the subject must not shield an otherwise-normal answer to a
    genuinely unrelated conceptual question."""
    seed_open_question(db_session, learner_id=demo_learner.learner_id, subject=biology_subject)
    captured: dict = {}
    with (
        patch_moderation(allowed=True),
        patch_shielding_match(matches=False),
        patch_search_passages([]),
        patch_grounded_stream_capturing(
            ["Because negative times negative is positive."],
            grounded_passage_ids=[],
            captured_kwargs=captured,
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "why does multiplying two negatives give a positive?"},
        )

    assert response.status_code == 200, response.text
    # stream_tutor_answer's own contract (client.py) omits "shielding"
    # from the actual wire payload entirely when it's None -- this
    # captures the outer call's kwargs, so None here is what proves
    # shielding didn't apply.
    assert captured.get("shielding") is None

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.shielded is False
    assert exchange.shielded_question_id is None


def test_no_open_question_answers_normally_and_skips_classification(client, db_session, session_id):
    """spec 016 US2: with nothing open at all, `determine_shielding`
    must short-circuit before ever calling the classifier -- forcing
    `classify_match` to raise proves it was never invoked."""
    captured: dict = {}
    with (
        patch_moderation(allowed=True),
        patch_shielding_match_failure(RuntimeError("must not be called")),
        patch_search_passages([]),
        patch_grounded_stream_capturing(
            ["A normal, unshielded answer."], grounded_passage_ids=[], captured_kwargs=captured
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "any question at all"}
        )

    assert response.status_code == 200, response.text
    assert captured.get("shielding") is None

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.shielded is False


def test_shielding_lifts_once_the_open_question_is_answered(
    client, db_session, session_id, demo_learner, biology_subject
):
    """spec 016 US3/SC-004: once a previously-shielded question has
    been answered, a follow-up tutor question about it is answered
    normally -- proven by forcing the classifier to raise, since a
    still-open question would otherwise be shielded via FR-010's
    fail-safe."""
    open_question = seed_open_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    with (
        patch_moderation(allowed=True),
        patch_shielding_match(matches=True),
        patch_search_passages([]),
        patch_grounded_stream(["Think it through first."], grounded_passage_ids=[]),
    ):
        first = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "just give me the answer"},
        )
    assert first.status_code == 200, first.text
    shielded_exchange = (
        db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    )
    assert shielded_exchange.shielded is True

    answer = client.post(f"/api/questions/{open_question.question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    with (
        patch_moderation(allowed=True),
        patch_shielding_match_failure(RuntimeError("must not be called -- no longer open")),
        patch_search_passages([]),
        patch_grounded_stream(["Sure, here's why that's the answer."], grounded_passage_ids=[]),
    ):
        follow_up = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "now that I answered it, can you explain that one?"},
        )
    assert follow_up.status_code == 200, follow_up.text

    exchanges = (
        db_session.query(TutorExchange)
        .filter(TutorExchange.session_id == session_id)
        .order_by(TutorExchange.created_at)
        .all()
    )
    assert len(exchanges) == 2
    assert exchanges[1].shielded is False
    assert exchanges[1].shielded_question_id is None


def test_shielding_lifts_once_the_assignment_is_cancelled(
    client, db_session, session_id, demo_learner, biology_subject
):
    """spec 016 US3/FR-006 (`/speckit-analyze` finding C1): a cancelled
    instructor-assigned attempt's still-unanswered question is no
    longer "open" -- shielding lifts without an answer ever being
    submitted."""
    from src.services.quiz_assignment.assignment import cancel_assignment

    _question, assignment = seed_open_quiz_assignment_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    with (
        patch_moderation(allowed=True),
        patch_shielding_match(matches=True),
        patch_search_passages([]),
        patch_grounded_stream(["Think it through first."], grounded_passage_ids=[]),
    ):
        first = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "just give me the answer"},
        )
    assert first.status_code == 200, first.text
    shielded_exchange = (
        db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    )
    assert shielded_exchange.shielded is True

    cancel_assignment(db_session, assignment=assignment)

    with (
        patch_moderation(allowed=True),
        patch_shielding_match_failure(RuntimeError("must not be called -- assignment cancelled")),
        patch_search_passages([]),
        patch_grounded_stream(["Sure, here's why that's the answer."], grounded_passage_ids=[]),
    ):
        follow_up = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "can you explain that one to me now?"},
        )
    assert follow_up.status_code == 200, follow_up.text

    exchanges = (
        db_session.query(TutorExchange)
        .filter(TutorExchange.session_id == session_id)
        .order_by(TutorExchange.created_at)
        .all()
    )
    assert len(exchanges) == 2
    assert exchanges[1].shielded is False
    assert exchanges[1].shielded_question_id is None


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


def test_503_retrieval_failure_marks_exchange_failed_not_stuck(client, db_session, session_id):
    """T038 grounding investigation (roadmap.md): a raw embedding-
    provider exception (e.g. a Voyage rate-limit/billing rejection) was
    previously left completely uncaught in `search_passages`, propagating
    as an unhandled 500 with no `TutorExchange` row, no audit-log event,
    no trace anywhere -- worse than finding H2's original deadlock, which
    at least left a row behind. Now maps to the same clean `503
    tutor_unavailable` the A2A-stream-open failure above already gets."""
    with (
        patch_moderation(allowed=True),
        patch_search_passages_failure(RuntimeError("embedding provider unavailable")),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "a question"}
        )
    assert response.status_code == 503, response.text
    assert response.json() == {"error": "tutor_unavailable"}

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.answer_text is None
    assert exchange.failed_at is not None

    # Not stuck behind a phantom in-flight exchange either.
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["all good now"], grounded_passage_ids=[]),
    ):
        retry = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "try again"}
        )
    assert retry.status_code == 200, retry.text


async def test_cancelled_retrieval_propagates_uncaught_and_marks_exchange_failed(
    client, db_session, session_id
):
    """PR #40 review finding: an earlier version of the retrieval-failure
    `except` block caught `asyncio.CancelledError`/`GeneratorExit`
    alongside `Exception` and unconditionally converted everything into
    `TutorUnavailableError` -- swallowing a real cancellation (client
    disconnect / Vercel timeout while `search_passages` is in flight)
    into a different exception type, breaking asyncio's cancellation
    contract. Calls `prepare_message` directly (not through `client`/
    `TestClient`) -- empirically, `TestClient`'s sync-to-async thread
    bridge re-raises a cancellation as `concurrent.futures.CancelledError`
    at its own `Future.result()` call site regardless of which exception
    type this code actually re-raises, so going through it can't tell
    this test apart from the bug it's guarding against."""
    session = db_session.get(TutoringSession, uuid.UUID(session_id))

    with (
        patch_moderation(allowed=True),
        patch_search_passages_failure(asyncio.CancelledError()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await prepare_message(db_session, session=session, question="a question")

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.answer_text is None
    assert exchange.failed_at is not None

    # Not stuck behind a phantom in-flight exchange either -- back
    # through the normal `client`/`TestClient` path, since this half
    # doesn't involve cancellation.
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["recovered answer"], grounded_passage_ids=[]),
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


def test_session_recovers_after_an_unexpected_exception_opening_the_stream(
    client, db_session, session_id
):
    """Found live against production (see roadmap.md's Milestone 9
    status): `prepare_message`'s `anext(stream)` call only caught
    `TutorUnavailableError`, not an arbitrary exception raised while
    opening the A2A stream (e.g. a misconfigured Tutor Agent endpoint) --
    that left the just-created exchange permanently `answer_text IS
    NULL AND failed_at IS NULL`, the same finding-H2 deadlock
    `test_session_recovers_after_an_unexpected_exception_mid_stream`
    already covers one step later."""
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_unexpected_exception_opening_stream(),
    ):
        with pytest.raises(ValueError, match="simulated unexpected bug opening the stream"):
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


def test_session_recovers_after_a_simulated_client_disconnect(client, db_session, session_id):
    """PR #34 review finding: `except Exception` alone doesn't catch a
    real client disconnect/Vercel timeout, which cancels the stream via
    `asyncio.CancelledError` -- a `BaseException` subclass, not an
    `Exception` subclass. contracts/api.md names this exact scenario as
    one that must set `failed_at`.

    Unlike the other mid-stream-failure tests, this does NOT assert
    `pytest.raises` -- verified empirically that a `CancelledError`
    raised inside the streaming generator is absorbed by Starlette's
    own cancellation handling (the same machinery a *real* disconnect
    triggers) rather than propagating to the caller. The client just
    gets an incomplete/empty response, matching contracts/api.md's "no
    learner-facing response for this case beyond the connection simply
    ending" -- what actually matters is that `except BaseException` ran
    and set `failed_at` before that absorption happens.
    """
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_disconnected_stream(["partial answer before the disconnect"]),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages", json={"question": "a question"}
        )
    # Can't assert "not 200" -- headers are already committed by the
    # time the cancellation happens, so 200 is the real, expected
    # status here (verified empirically). What must never happen is a
    # `done` event reaching the client: that would mean a future
    # regression turned this into a silently-truncated-but-"successful"
    # response (PR #34 review nit) instead of the incomplete one
    # contracts/api.md calls for.
    events = parse_sse_events(response.text)
    assert not any("done" in event for event in events), events

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
