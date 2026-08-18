"""Integration test: `POST /api/questions/{id}/answer` extended for
quiz questions (contracts/api.md, research.md §4), T014.

`quiz_difficulty_adjusted` event logged per answered quiz question
(FR-009), and `QuizSession.status` flips to `completed` when the
answered-question count reaches `question_count`.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_quiz_difficulty_adjusted_event_logged_per_answer(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 3}
        )
    quiz = start.json()
    question_id = quiz["question"]["question_id"]

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question_id),
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .all()
    )
    assert len(events) == 1
    payload = events[0].payload
    assert payload["quiz_session_id"] == quiz["quiz_session_id"]
    assert payload["prior_band"] == "easy"
    assert payload["new_band"] == "easy"
    assert payload["streak_direction"] == "correct"
    assert payload["streak_length_at_decision"] == 1
    assert payload["held_at_bound"] is False


def test_quiz_completes_when_answered_count_reaches_question_count(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 1}
        )
    quiz = start.json()

    answer = client.post(
        f"/api/questions/{quiz['question']['question_id']}/answer", json={"response": 0}
    )
    assert answer.status_code == 200, answer.text

    quiz_row = db_session.get(QuizSession, uuid.UUID(quiz["quiz_session_id"]))
    db_session.refresh(quiz_row)
    assert quiz_row.status == QuizSessionStatus.COMPLETED
    assert quiz_row.completed_at is not None


def test_quiz_still_in_progress_below_question_count(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    quiz = start.json()

    answer = client.post(
        f"/api/questions/{quiz['question']['question_id']}/answer", json={"response": 0}
    )
    assert answer.status_code == 200, answer.text

    quiz_row = db_session.get(QuizSession, uuid.UUID(quiz["quiz_session_id"]))
    db_session.refresh(quiz_row)
    assert quiz_row.status == QuizSessionStatus.IN_PROGRESS
    assert quiz_row.completed_at is None


def test_non_quiz_answer_unaffected(db_session, demo_learner, algebra_subject):
    """A non-quiz question's answer response is byte-for-byte unchanged
    (research.md §4's "contract unmodified" claim)."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        placement = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    assert placement.status_code == 200, placement.text
    question = placement.json()["questions"][0]

    answer = client.post(
        f"/api/questions/{question['question_id']}/answer", json={"response": 0}
    )
    assert answer.status_code == 200, answer.text
    assert set(answer.json().keys()) == {
        "correct",
        "topic_id",
        "prior_p_mastery",
        "posterior_p_mastery",
        "band",
    }

    quiz_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question["question_id"]),
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .count()
    )
    assert quiz_events == 0
