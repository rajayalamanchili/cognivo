"""Contract test: `GET /api/learners/{id}/mastery-state` surfaces
decay-adjusted effective mastery alongside raw/peak mastery (spec 025
User Story 2, FR-005/FR-006).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime

import pytest
from fastapi.testclient import TestClient

from src.models.mastery_state import MasteryState
from src.services.mastery.decay import GRACE_PERIOD, HALF_LIFE, effective_mastery_for_review

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_topic_within_grace_period_reports_effective_equal_to_raw(
    client, db_session, demo_learner, algebra_subject
):
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(
        MasteryState(
            learner_id=demo_learner.learner_id,
            subject_id="algebra-1",
            topic_id="integers-and-operations",
            p_mastery=0.8,
            update_count=3,
            consecutive_mastered_observations=2,
            updated_at=now,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200
    entry = next(
        t
        for t in response.json()["topics"]
        if t["topic_id"] == "integers-and-operations"
    )
    assert entry["p_mastery"] == 0.8
    assert entry["effective_p_mastery"] == 0.8


def test_topic_decayed_past_grace_reports_effective_below_raw(
    client, db_session, demo_learner, algebra_subject
):
    backdated = datetime.datetime.now(datetime.UTC) - GRACE_PERIOD - HALF_LIFE * 2
    db_session.add(
        MasteryState(
            learner_id=demo_learner.learner_id,
            subject_id="algebra-1",
            topic_id="integers-and-operations",
            p_mastery=0.8,
            update_count=3,
            consecutive_mastered_observations=2,
            updated_at=backdated,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200
    entry = next(
        t
        for t in response.json()["topics"]
        if t["topic_id"] == "integers-and-operations"
    )
    assert entry["p_mastery"] == 0.8
    assert entry["effective_p_mastery"] < 0.8
    # FR-006: must equal decay.py's own output, not a separate computation.
    # The route computes `now` independently per-request (a few ms after
    # this assertion's own `now`), so compare with a tight tolerance
    # rather than requiring byte-identical floats.
    expected = effective_mastery_for_review(
        0.8, updated_at=backdated, now=datetime.datetime.now(datetime.UTC)
    )
    assert abs(entry["effective_p_mastery"] - expected) < 1e-6


def test_topic_with_no_mastery_state_has_no_effective_mastery(
    client, db_session, demo_learner, algebra_subject
):
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200
    entry = next(
        t
        for t in response.json()["topics"]
        if t["topic_id"] == "integers-and-operations"
    )
    assert entry["status"] == "unknown"
    assert entry["p_mastery"] is None
    assert entry["effective_p_mastery"] is None
