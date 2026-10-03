"""Integration test: `GET /api/learners/{id}/activity-summary`
(027-learner-ui-redesign FR-009, Dashboard's "questions this week" tile).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType

_TOPIC_ID = "integers-and-operations"


def _record_answer_submitted(db_session, *, learner_id, subject_id, created_at, correct=True):
    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            subject_id=subject_id,
            topic_id=_TOPIC_ID,
            payload={"correct": correct},
            created_at=created_at,
        )
    )


def test_counts_only_answers_within_the_trailing_week(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    _record_answer_submitted(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        created_at=now - datetime.timedelta(days=1),
        correct=True,
    )
    _record_answer_submitted(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        created_at=now - datetime.timedelta(days=3),
        correct=False,
    )
    # Outside the 7-day window -- must not be counted.
    _record_answer_submitted(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        created_at=now - datetime.timedelta(days=10),
        correct=True,
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/activity-summary",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["questions_this_week"] == 2
    assert body["questions_correct_this_week"] == 1


def test_no_events_returns_zero_not_404(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/activity-summary",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["questions_this_week"] == 0


def test_other_event_types_not_counted(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    # Different event type on the same subject/topic -- must not be counted.
    db_session.add(
        AssessmentEvent(
            learner_id=demo_learner.learner_id,
            event_type=AssessmentEventType.NEXT_TOPIC_SELECTED,
            subject_id="algebra-1",
            topic_id=_TOPIC_ID,
            payload={},
            created_at=now,
        )
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/activity-summary",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["questions_this_week"] == 0
