"""Integration test: `GET /api/learners/{id}/topics/{id}/mastery-history`
(spec 025 User Story 5, FR-012).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion

_TOPIC_ID = "integers-and-operations"


def _record_mastery_update(db_session, *, learner_id, subject_id, posterior, created_at):
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=_TOPIC_ID,
        difficulty=DifficultyBand.MEDIUM,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="stem",
        options=["a", "b"],
        answer_key={"correct_index": 0},
        validation_status=ValidationStatus.VALID,
        shown_at=created_at,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.MASTERY_UPDATED,
            subject_id=subject_id,
            topic_id=_TOPIC_ID,
            question_id=question.question_id,
            payload={"prior_p_mastery": None, "posterior_p_mastery": posterior},
            created_at=created_at,
        )
    )


def test_multiple_updates_returned_in_chronological_order(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    # Inserted out of order -- the route must sort, not trust insert order.
    _record_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        posterior=0.6,
        created_at=now - datetime.timedelta(days=1),
    )
    _record_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        posterior=0.3,
        created_at=now - datetime.timedelta(days=3),
    )
    _record_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        posterior=0.8,
        created_at=now,
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topics/{_TOPIC_ID}/mastery-history",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    points = response.json()["points"]
    assert [p["p_mastery"] for p in points] == [0.3, 0.6, 0.8]
    assert points[0]["recorded_at"] < points[1]["recorded_at"] < points[2]["recorded_at"]


def test_single_update_returns_one_point(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    _record_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        posterior=0.5,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topics/{_TOPIC_ID}/mastery-history",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["points"]) == 1


def test_no_mastery_state_returns_empty_list_not_404(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topics/{_TOPIC_ID}/mastery-history",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["points"] == []
