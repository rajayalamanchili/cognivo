"""Integration test: `GET /api/learners/{id}/mastery-state`'s
`recently_refreshed_topic_id` field (027-learner-ui-redesign gap-closing
pass, Dashboard's "Refreshed!" banner).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.mastery_state import MasteryState

_TOPIC_ID = "integers-and-operations"


def _mastery_updated_event(
    db_session, *, learner_id, subject_id, topic_id, prior, posterior, created_at
):
    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.MASTERY_UPDATED,
            subject_id=subject_id,
            topic_id=topic_id,
            payload={"prior_p_mastery": prior, "posterior_p_mastery": posterior},
            created_at=created_at,
        )
    )


def _mastered_state(db_session, *, learner_id, subject_id, topic_id):
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            p_mastery=0.9,
            update_count=3,
            consecutive_mastered_observations=2,
        )
    )


def test_topic_that_recrossed_the_line_within_the_window_is_reported(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    learner_id = demo_learner.learner_id
    # First reached mastered a while ago...
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.6,
        posterior=0.8,
        created_at=now - datetime.timedelta(days=60),
    )
    # ...decayed/regressed below the line...
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.8,
        posterior=0.5,
        created_at=now - datetime.timedelta(days=30),
    )
    # ...and crossed back above it yesterday.
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.5,
        posterior=0.85,
        created_at=now - datetime.timedelta(days=1),
    )
    _mastered_state(db_session, learner_id=learner_id, subject_id="algebra-1", topic_id=_TOPIC_ID)
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recently_refreshed_topic_id"] == _TOPIC_ID


def test_first_time_mastery_is_not_reported_as_refreshed(
    db_session, demo_learner, algebra_subject
):
    """FR guard mirrored from `refreshed_from_bands`: crossing the line
    for the very first time is not a "refresh" -- there was nothing to
    recover."""
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    learner_id = demo_learner.learner_id
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.6,
        posterior=0.85,
        created_at=now - datetime.timedelta(days=1),
    )
    _mastered_state(db_session, learner_id=learner_id, subject_id="algebra-1", topic_id=_TOPIC_ID)
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recently_refreshed_topic_id"] is None


def test_crossing_outside_the_trailing_window_is_not_reported(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    learner_id = demo_learner.learner_id
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.6,
        posterior=0.8,
        created_at=now - datetime.timedelta(days=90),
    )
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.8,
        posterior=0.5,
        created_at=now - datetime.timedelta(days=60),
    )
    # Crossed back above the line, but 10 days ago -- outside the
    # default 7-day trailing window.
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.5,
        posterior=0.85,
        created_at=now - datetime.timedelta(days=10),
    )
    _mastered_state(db_session, learner_id=learner_id, subject_id="algebra-1", topic_id=_TOPIC_ID)
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recently_refreshed_topic_id"] is None


def test_topic_currently_not_mastered_is_not_reported_even_if_it_once_crossed(
    db_session, demo_learner, algebra_subject
):
    """A topic that crossed back above the line and then decayed/
    regressed again since isn't still shown as "refreshed" -- only its
    *current* band matters, per `find_recently_refreshed_topic`'s own
    docstring."""
    from src.api.main import app

    now = datetime.datetime.now(datetime.UTC)
    learner_id = demo_learner.learner_id
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.6,
        posterior=0.8,
        created_at=now - datetime.timedelta(days=60),
    )
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.8,
        posterior=0.5,
        created_at=now - datetime.timedelta(days=30),
    )
    _mastery_updated_event(
        db_session,
        learner_id=learner_id,
        subject_id="algebra-1",
        topic_id=_TOPIC_ID,
        prior=0.5,
        posterior=0.85,
        created_at=now - datetime.timedelta(days=1),
    )
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id="algebra-1",
            topic_id=_TOPIC_ID,
            p_mastery=0.3,
            update_count=4,
            consecutive_mastered_observations=0,
        )
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recently_refreshed_topic_id"] is None


def test_no_mastery_updated_events_is_not_reported(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": "algebra-1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recently_refreshed_topic_id"] is None
