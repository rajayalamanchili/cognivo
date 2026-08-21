"""Integration test: a free-text question generated inside a
`QuizSession` is graded and feeds `record_quiz_answer`'s
difficulty-adjustment logic identically to any other in-quiz question
type, with no separate integration path (spec 007 FR-011), T024.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.free_text_helpers import (
    FREE_TEXT_TOPIC_ID,
    patch_free_text_generation,
    patch_grading_result,
    patch_moderation,
)


def test_free_text_quiz_question_feeds_difficulty_adjustment(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)

    with patch_free_text_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [FREE_TEXT_TOPIC_ID], "question_count": 1}
        )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["question"]["question_type"] == "free_text"
    question_id = body["question"]["question_id"]

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=["a"], criteria_missed=[]),
    ):
        answer = client.post(
            f"/api/questions/{question_id}/answer",
            json={"response": "x is independent, y is dependent."},
        )
    assert answer.status_code == 200, answer.text

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question_id,
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .all()
    )
    assert len(events) == 1

    summary = client.get(f"/api/quizzes/{body['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["status"] == "completed"
