"""Integration test: ordinary untimed practice is provably unaffected
by this feature (spec 022 FR-009, quickstart.md Scenario 3 step 4).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.quiz_helpers import patch_generation


def test_ordinary_next_question_has_no_practice_session_id(
    db_session, demo_learner, algebra_subject
):
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

    with patch_generation():
        next_q = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )
    assert next_q.status_code == 200, next_q.text
    question_id = next_q.json()["question_id"]

    from src.models.generated_question import GeneratedQuestion

    question = db_session.get(GeneratedQuestion, question_id)
    assert question.practice_session_id is None

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 1})
    assert answer.status_code == 200, answer.text

    ended_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .all()
    )
    assert len(ended_events) == 0
