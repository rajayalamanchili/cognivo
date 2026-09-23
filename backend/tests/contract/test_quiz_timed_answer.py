"""Contract tests: `POST /api/questions/{id}/answer` expiry rejection
for a timed quiz (spec 022 FR-004/FR-006/SC-003, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.enums import QuizSessionStatus
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_answer_before_expiry_scores_identically_to_untimed(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        timed_start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert timed_start.status_code == 200, timed_start.text
    timed_question = timed_start.json()["question"]

    with patch_generation():
        untimed_start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    assert untimed_start.status_code == 200, untimed_start.text
    untimed_question = untimed_start.json()["question"]

    timed_answer = client.post(
        f"/api/questions/{timed_question['question_id']}/answer", json={"response": 1}
    )
    untimed_answer = client.post(
        f"/api/questions/{untimed_question['question_id']}/answer", json={"response": 1}
    )
    assert timed_answer.status_code == 200, timed_answer.text
    assert untimed_answer.status_code == 200, untimed_answer.text
    assert timed_answer.json()["correct"] == untimed_answer.json()["correct"]


def test_answer_after_expiry_is_rejected_before_scoring(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    question_id = start.json()["question"]["question_id"]
    quiz_session_id = start.json()["quiz_session_id"]

    quiz = db_session.get(QuizSession, quiz_session_id)
    quiz.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    db_session.commit()

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 1})
    assert answer.status_code == 409, answer.text

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.ENDED_EARLY
