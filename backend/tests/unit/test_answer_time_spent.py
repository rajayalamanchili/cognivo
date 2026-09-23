"""Integration-shaped test (kept in tests/unit per tasks.md T012):
`time_spent_seconds` is recorded on the `answer_submitted` event for
every answered question, no timer involved (spec 022 FR-011,
research.md §6). Timed-quiz/timed-practice coverage lives in T017/T028
(Phase 3/4, not yet implemented).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def _answer_event_for(db_session, question_id):
    return (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .first()
    )


def test_placement_answer_records_time_spent(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text

    event = _answer_event_for(db_session, questions[0]["question_id"])
    assert event is not None
    assert isinstance(event.payload["time_spent_seconds"], int)
    assert event.payload["time_spent_seconds"] >= 0


def test_untimed_practice_answer_records_time_spent(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    # Ordinary practice requires placement to be completed first for
    # this subject (a pre-existing rule, unrelated to this feature).
    with patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        placement_questions = start.json()["questions"]
        answers = [
            {"question_id": q["question_id"], "response": 1} for q in placement_questions
        ]
        submit = client.post(
            f"/api/placement/{start.json()['placement_session_id']}/submit",
            json={"answers": answers},
        )
        assert submit.status_code == 200, submit.text

        next_q = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )
    assert next_q.status_code == 200, next_q.text
    question = next_q.json()

    answer = client.post(f"/api/questions/{question['question_id']}/answer", json={"response": 1})
    assert answer.status_code == 200, answer.text

    event = _answer_event_for(db_session, question["question_id"])
    assert event is not None
    assert isinstance(event.payload["time_spent_seconds"], int)
    assert event.payload["time_spent_seconds"] >= 0


def test_untimed_quiz_answer_records_time_spent(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    assert start.status_code == 200, start.text
    question = start.json()["question"]

    answer = client.post(f"/api/questions/{question['question_id']}/answer", json={"response": 1})
    assert answer.status_code == 200, answer.text

    event = _answer_event_for(db_session, question["question_id"])
    assert event is not None
    assert isinstance(event.payload["time_spent_seconds"], int)
    assert event.payload["time_spent_seconds"] >= 0
