"""Integration test: a concurrent manual end-now/expiry racing a
free-text answer's own (LLM-bound) grading call (spec 022, PR #83
review finding). `answer_question` checks the session's status before
grading starts, but free-text/multi-step grading is an A2A call wide
enough for the session to end on a concurrent request while it's still
in flight -- research.md §1 requires that answer be rejected, not
silently scored. `_reject_if_timed_session_ended` (api/routes/
questions.py) re-runs the same check right after grading completes;
this test simulates the interleaving by having the mocked grading call
itself commit the "concurrent" end-now via a second, separate DB
session before returning its result.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.practice_session import PracticeSession
from src.services.grading_client.client import GradingResult
from src.services.quiz.session import end_session_manually
from tests.integration.free_text_helpers import (
    make_free_text_topic_next_up,
    patch_free_text_generation,
    patch_grading_result,
    patch_moderation,
)


def test_free_text_answer_rejected_when_session_ends_mid_grading(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    make_free_text_topic_next_up(db_session, demo_learner.learner_id, algebra_subject.subject_id)

    with patch_free_text_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    practice_session_id = start.json()["practice_session_id"]
    question_id = start.json()["question"]["question_id"]
    assert start.json()["question"]["question_type"] == "free_text"

    def _end_practice_concurrently(*args, **kwargs):
        session = db_session.get(PracticeSession, uuid.UUID(practice_session_id))
        end_session_manually(db_session, session=session, session_type="practice")
        db_session.commit()
        return GradingResult(
            correct=True,
            graduated_score=1.0,
            criteria_met=["identifies both variables"],
            criteria_missed=[],
            grading_logic_version="v1",
        )

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, side_effect=_end_practice_concurrently),
    ):
        answer = client.post(
            f"/api/questions/{question_id}/answer",
            json={"response": "x is independent, y is dependent"},
        )

    assert answer.status_code == 409, answer.text

    answered = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question_id),
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .count()
    )
    assert answered == 0  # rejected, not silently scored (research.md §1)

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["end_reason"] == "manually_ended_early"
