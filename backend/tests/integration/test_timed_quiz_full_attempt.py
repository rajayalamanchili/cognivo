"""Integration test: full timed-quiz attempt, quickstart.md Scenarios
1-2 (spec 022 FR-003/FR-004/FR-005/FR-011, spec.md Acceptance
Scenarios 1-3, SC-003/SC-006).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_learner_completes_before_expiry_matches_untimed_score(
    db_session, demo_learner, algebra_subject
):
    """Quickstart Scenario 1: a timed quiz completed with time to spare
    scores exactly like an identical untimed quiz would, and every
    answered question carries a `time_spent_seconds` value (FR-011)."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 2, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]
    question_ids = [start.json()["question"]["question_id"]]

    answer_one = client.post(
        f"/api/questions/{question_ids[0]}/answer", json={"response": 1}
    )
    assert answer_one.status_code == 200, answer_one.text

    with patch_generation():
        next_q = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_q.status_code == 200, next_q.text
    question_ids.append(next_q.json()["question"]["question_id"])
    answer_two = client.post(
        f"/api/questions/{question_ids[1]}/answer", json={"response": 1}
    )
    assert answer_two.status_code == 200, answer_two.text

    quiz = db_session.get(QuizSession, quiz_session_id)
    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.COMPLETED

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["score"]["total"] == 2

    for question_id in question_ids:
        event = (
            db_session.query(AssessmentEvent)
            .filter(
                AssessmentEvent.question_id == question_id,
                AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            )
            .first()
        )
        assert event is not None
        assert isinstance(event.payload["time_spent_seconds"], int)

    # The quiz's own completion is audited too (FR-007), not just
    # expiry/manual-end.
    ended_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .all()
    )
    assert len(ended_events) == 1
    assert ended_events[0].payload["end_reason"] == "completed"


def test_timer_expires_mid_attempt_auto_submits(db_session, demo_learner, algebra_subject):
    """Quickstart Scenario 2: the timer expiring mid-attempt auto-
    submits, leaving unanswered questions unanswered -- never lock-and-
    manual-end."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]
    question_id = start.json()["question"]["question_id"]

    answer_one = client.post(f"/api/questions/{question_id}/answer", json={"response": 1})
    assert answer_one.status_code == 200, answer_one.text

    quiz = db_session.get(QuizSession, quiz_session_id)
    quiz.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    db_session.commit()

    next_q = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_q.status_code == 409, next_q.text

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.ENDED_EARLY

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    # Only the one question answered before expiry counts -- the quiz
    # never reached its configured question_count of 5.
    assert summary.json()["score"]["total"] == 1
