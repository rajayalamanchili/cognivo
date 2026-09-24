"""Integration test: a concurrent manual end-now/expiry racing a timed
session's own next-question generation (spec 022, PR #83 review
finding). `check_and_expire_if_needed` deliberately releases its row
lock before the LLM-bound generation call so that call doesn't block a
concurrent end-now/expiry -- but that leaves a window where the session
can end mid-generation. `session_still_in_progress` (services/quiz/
session.py) re-checks right before the freshly-generated question is
returned/persisted; these tests simulate the interleaving by having the
mocked generation call itself commit the "concurrent" end-now via a
second, separate DB session before returning its draft.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.generated_question import GeneratedQuestion
from src.models.practice_session import PracticeSession
from src.models.quiz_session import QuizSession
from src.services.quiz.session import end_session_manually
from tests.integration.quiz_helpers import draft_json, patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def _end_quiz_concurrently(db_session, quiz_session_id: uuid.UUID) -> None:
    """Simulates request B: a manual "end now" click that commits, on
    its own DB connection, while request A's generation call (below) is
    still in flight."""
    quiz = db_session.get(QuizSession, quiz_session_id)
    end_session_manually(db_session, session=quiz, session_type="quiz")
    db_session.commit()


def test_quiz_next_question_race_does_not_persist_after_concurrent_end(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    async def _generate_then_race_ahead(agent, session_service):
        _end_quiz_concurrently(db_session, uuid.UUID(quiz_session_id))
        return draft_json("racing stem")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_generate_then_race_ahead),
    ):
        next_q = client.get(f"/api/quizzes/{quiz_session_id}/next-question")

    assert next_q.status_code == 200, next_q.text
    body = next_q.json()
    assert body["status"] == "ended_early"
    assert body["question"] is None

    count = (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == uuid.UUID(quiz_session_id))
        .count()
    )
    assert count == 1  # only the first (start-time) question, no second one

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


def _complete_placement(client: TestClient, subject_id: str) -> None:
    with patch_generation():
        start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text


def test_practice_next_question_race_rolls_back_after_concurrent_end(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)
    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    practice_session_id = start.json()["practice_session_id"]

    def _end_practice_concurrently() -> None:
        session = db_session.get(PracticeSession, uuid.UUID(practice_session_id))
        end_session_manually(db_session, session=session, session_type="practice")
        db_session.commit()

    async def _generate_then_race_ahead(agent, session_service):
        _end_practice_concurrently()
        return draft_json("racing stem")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_generate_then_race_ahead),
    ):
        next_q = client.get(f"/api/practice-sessions/{practice_session_id}/next-question")

    assert next_q.status_code == 409, next_q.text

    count = (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.practice_session_id == uuid.UUID(practice_session_id))
        .count()
    )
    assert count == 1  # only the first (start-time) question -- the race got rolled back

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
