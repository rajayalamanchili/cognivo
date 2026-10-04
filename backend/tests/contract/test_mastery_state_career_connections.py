"""Contract test: `GET /api/learners/{id}/mastery-state` surfaces
`career_connections` for the owning guardian, empty when the learner's
preference is off, and `require_learner_ownership_if_real()` still 403s
a non-owning guardian (spec 039 FR-003/FR-006).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import pytest

from src.models.learner_profile import LearnerProfile
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import validate_content_artifact
from tests.integration.quiz_assignment_helpers import (
    register_guardian_with_learner,
)

pytestmark = pytest.mark.usefixtures("database_available")

_CAREER_CONNECTION = {
    "career": "Civil Engineer",
    "description": "Civil engineers use the same equations to calculate load limits on bridges.",
}


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def tagged_subject(db_session):
    artifact = validate_content_artifact(
        {
            "subject_id": "mastery-career-connections-test-subject",
            "display_name": "Mastery Career Connections Test Subject",
            "content_version": "1.0.0",
            "topics": [
                {
                    "topic_id": "topic-a",
                    "display_name": "Topic A",
                    "skill_definition": {"summary": "Topic A."},
                    "career_connection": _CAREER_CONNECTION,
                },
                {
                    "topic_id": "topic-b",
                    "display_name": "Topic B",
                    "skill_definition": {"summary": "Topic B, no authored connection."},
                },
            ],
        }
    )
    persist_content_artifact(db_session, artifact)
    return artifact


def test_owning_guardian_sees_career_connections_field(client, db_session, tagged_subject):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-owner@example.com", learner_name="Owned Learner"
    )

    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": tagged_subject.subject_id},
    )

    assert response.status_code == 200
    [entry] = response.json()["career_connections"]
    assert entry["topic_id"] == "topic-a"
    assert entry["career"] == _CAREER_CONNECTION["career"]
    assert entry["description"] == _CAREER_CONNECTION["description"]


def test_disabled_preference_returns_empty_career_connections(client, db_session, tagged_subject):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-disabled@example.com", learner_name="Disabled Learner"
    )
    learner = db_session.get(LearnerProfile, learner_id)
    learner.career_connections_enabled = False
    db_session.commit()

    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": tagged_subject.subject_id},
    )

    assert response.status_code == 200
    assert response.json()["career_connections"] == []


def test_non_owning_guardian_still_403s(client, tagged_subject):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-owner-2@example.com", learner_name="Owned Learner 2"
    )
    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="career-intruder@example.com", learner_name="Unrelated Learner"
    )

    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": tagged_subject.subject_id},
    )

    assert response.status_code == 403
