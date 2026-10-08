"""Integration test: `POST /api/learners/{learner_id}/rosters/{roster_id}/
assignments` (spec 043 contracts/api-changes.md §6, research.md §6), T021.

A guardian self-assigning a quiz to their own learner, scoped to a
default-instructor-owned roster only.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.quiz_assignment_helpers import (
    create_roster,
    join_roster,
    register_guardian_with_learner,
    register_instructor,
    seed_and_login_default_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")

_ENTRY_TOPIC = "integers-and-operations"


@pytest.fixture()
def default_instructor_email():
    return f"guardian-assign-default-{uuid.uuid4()}@example.com"


@pytest.fixture()
def client(db_session, monkeypatch, default_instructor_email):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", default_instructor_email)
    return TestClient(app, base_url="https://testserver")


def _assign(client, *, learner_id, roster_id, question_count=3, due_at=None):
    return client.post(
        f"/api/learners/{learner_id}/rosters/{roster_id}/assignments",
        json={
            "topic_ids": [_ENTRY_TOPIC],
            "question_count": question_count,
            "due_at": due_at,
        },
    )


def test_success_matches_instructor_side_shape_and_audits_the_default_instructor(
    client, algebra_subject, db_session, default_instructor_email
):
    default_instructor_id = seed_and_login_default_instructor(
        client, db_session, default_instructor_email
    )
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-parent@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    response = _assign(client, learner_id=learner_id, roster_id=roster_id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["roster_id"] == roster_id
    assert body["subject_id"] == algebra_subject.subject_id
    assert body["topic_ids"] == [_ENTRY_TOPIC]
    assert body["question_count"] == 3
    assert body["target_learner_ids"] == [learner_id]

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == uuid.UUID(learner_id),
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_ASSIGNMENT_CREATED,
        )
        .one()
    )
    assert event.payload["instructor_id"] == default_instructor_id


def test_unknown_roster_id_returns_404(client, db_session, default_instructor_email):
    seed_and_login_default_instructor(client, db_session, default_instructor_email)
    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-parent-404@example.com", learner_name="Learner"
    )

    response = _assign(client, learner_id=learner_id, roster_id=str(uuid.uuid4()))
    assert response.status_code == 404, response.text


def test_not_your_learner_returns_403(
    client, algebra_subject, db_session, default_instructor_email
):
    seed_and_login_default_instructor(client, db_session, default_instructor_email)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, owned_learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-owner@example.com", learner_name="Owned"
    )
    join_roster(client, learner_id=owned_learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="guardian-assign-intruder@example.com", learner_name="Intruder"
    )

    response = _assign(client, learner_id=owned_learner_id, roster_id=roster_id)
    assert response.status_code == 403, response.text


def test_not_enrolled_returns_403(client, algebra_subject, db_session, default_instructor_email):
    seed_and_login_default_instructor(client, db_session, default_instructor_email)
    roster_id, _join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-not-enrolled@example.com", learner_name="Learner"
    )

    response = _assign(client, learner_id=learner_id, roster_id=roster_id)
    assert response.status_code == 403, response.text


def test_non_default_instructor_roster_returns_403(
    client, algebra_subject, db_session, default_instructor_email
):
    seed_and_login_default_instructor(client, db_session, default_instructor_email)
    default_roster_id, default_join_code = create_roster(
        client, subject_id=algebra_subject.subject_id
    )

    client.post("/api/auth/logout")
    register_instructor(client, "guardian-assign-other-teacher@example.com")
    other_roster_id, other_join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-both-rosters@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=default_join_code)
    join_roster(client, learner_id=learner_id, join_code=other_join_code)

    response = _assign(client, learner_id=learner_id, roster_id=other_roster_id)
    assert response.status_code == 403, response.text

    # Sanity check: the same learner can still self-assign on the
    # default instructor's own roster.
    ok_response = _assign(client, learner_id=learner_id, roster_id=default_roster_id)
    assert ok_response.status_code == 201, ok_response.text


def test_unset_default_instructor_env_var_denies_every_guardian(
    client, algebra_subject, db_session, default_instructor_email, monkeypatch
):
    """Claude Code Review finding on PR #111: `get_default_instructor`
    resolves by env var per request, so a misconfigured environment
    (unset after the roster was created) must deny cleanly -- not 500 --
    rather than silently falling back to any looser check."""
    seed_and_login_default_instructor(client, db_session, default_instructor_email)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="guardian-assign-env-misconfig@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    monkeypatch.delenv("DEFAULT_INSTRUCTOR_EMAIL", raising=False)

    response = _assign(client, learner_id=learner_id, roster_id=roster_id)
    assert response.status_code == 403, response.text
