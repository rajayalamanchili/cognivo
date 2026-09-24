"""Integration test: full timed-practice session, quickstart.md
Scenario 3 (spec 022 FR-001/FR-003/FR-008/FR-011, spec.md User Story 2
Acceptance Scenarios, SC-006).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.generated_question import GeneratedQuestion
from tests.integration.quiz_helpers import patch_generation


def test_timed_practice_session_topic_hops_within_one_subject(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        placement_start = client.post(
            f"/api/subjects/{algebra_subject.subject_id}/placement/start"
        )
    assert placement_start.status_code == 200, placement_start.text
    placement_questions = placement_start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in placement_questions]
    submit = client.post(
        f"/api/placement/{placement_start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text

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
    question_ids = [start.json()["question"]["question_id"]]

    answer_one = client.post(
        f"/api/questions/{question_ids[0]}/answer", json={"response": 1}
    )
    assert answer_one.status_code == 200, answer_one.text

    with patch_generation():
        next_q = client.get(f"/api/practice-sessions/{practice_session_id}/next-question")
    assert next_q.status_code == 200, next_q.text
    question_ids.append(next_q.json()["question"]["question_id"])
    answer_two = client.post(
        f"/api/questions/{question_ids[1]}/answer", json={"response": 1}
    )
    assert answer_two.status_code == 200, answer_two.text

    # Every question generated in this session carries the same
    # practice_session_id, all within the one subject started with.
    for question_id in question_ids:
        question = db_session.get(GeneratedQuestion, question_id)
        assert str(question.practice_session_id) == practice_session_id
        assert question.subject_id == algebra_subject.subject_id

    # FR-011/SC-006: every answered question in this timed practice
    # session has a time_spent_seconds value.
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
