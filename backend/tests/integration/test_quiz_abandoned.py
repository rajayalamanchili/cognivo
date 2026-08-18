"""Integration test (SC-005, FR-006, User Story 2), T031.

Start a quiz, answer some but not all of its questions, then stop --
confirm `MasteryState` already reflects the answered questions and
`QuizSession.status` is still `in_progress` (no distinct "abandoned"
status, spec.md Key Entities) -- no new production code, this is
verification of behavior FR-006 already requires.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.enums import QuizSessionStatus
from src.models.mastery_state import MasteryState
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_abandoned_quiz_keeps_mastery_effect_of_answered_questions(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 6}
        )
    assert start.status_code == 200, start.text
    quiz = start.json()

    # Answer 2 of the quiz's 6 questions, then stop -- never call
    # next-question again (the "closes the browser" scenario).
    answer_one = client.post(
        f"/api/questions/{quiz['question']['question_id']}/answer", json={"response": 0}
    )
    assert answer_one.status_code == 200, answer_one.text

    with patch_generation():
        next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
    assert next_q.status_code == 200, next_q.text
    answer_two = client.post(
        f"/api/questions/{next_q.json()['question']['question_id']}/answer",
        json={"response": 0},
    )
    assert answer_two.status_code == 200, answer_two.text

    # MasteryState already reflects both answered questions.
    mastery_state = db_session.get(
        MasteryState,
        (demo_learner.learner_id, algebra_subject.subject_id, _ENTRY_TOPIC),
    )
    assert mastery_state is not None
    assert mastery_state.update_count == 2

    # QuizSession is still in_progress -- no distinct "abandoned" status.
    quiz_row = db_session.get(QuizSession, uuid.UUID(quiz["quiz_session_id"]))
    db_session.refresh(quiz_row)
    assert quiz_row.status == QuizSessionStatus.IN_PROGRESS
    assert quiz_row.completed_at is None

    # The quiz's own completion summary reflects only the 2 answered so
    # far (partial tally), not an error.
    summary = client.get(f"/api/quizzes/{quiz['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["status"] == "in_progress"
    assert summary.json()["score"]["total"] == 2
