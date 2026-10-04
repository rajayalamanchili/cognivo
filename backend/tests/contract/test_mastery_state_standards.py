"""Contract test: `GET /api/learners/{id}/mastery-state` surfaces
standards coverage for the owning guardian, and `require_learner_
ownership_if_real()` still 403s a non-owning guardian (spec 038 FR-004,
Clarifications).

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import pytest

from src.models.mastery_state import MasteryState
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import validate_content_artifact
from tests.integration.quiz_assignment_helpers import (
    register_guardian_with_learner,
)

pytestmark = pytest.mark.usefixtures("database_available")

_STANDARD = {
    "framework": "Common Core Math",
    "code": "CCSS.MATH.CONTENT.6.NS.C.5",
    "title": "Understand that positive and negative numbers represent opposite quantities.",
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
            "subject_id": "mastery-standards-test-subject",
            "display_name": "Mastery Standards Test Subject",
            "content_version": "1.0.0",
            "grade_bands": [6],
            "topics": [
                {
                    "topic_id": "topic-a",
                    "display_name": "Topic A",
                    "grade": 6,
                    "skill_definition": {"summary": "Topic A."},
                    "standards": [_STANDARD],
                }
            ],
        }
    )
    persist_content_artifact(db_session, artifact)
    return artifact


def test_owning_guardian_sees_standards_field(client, db_session, tagged_subject):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="standards-owner@example.com", learner_name="Owned Learner"
    )
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id=tagged_subject.subject_id,
            topic_id="topic-a",
            p_mastery=0.9,
            consecutive_mastered_observations=2,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": tagged_subject.subject_id},
    )

    assert response.status_code == 200
    [entry] = response.json()["standards"]
    assert entry["framework"] == _STANDARD["framework"]
    assert entry["code"] == _STANDARD["code"]
    assert entry["title"] == _STANDARD["title"]
    assert entry["topic_ids"] == ["topic-a"]
    assert entry["status"] == "met"


def test_non_owning_guardian_still_403s(client, tagged_subject):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="standards-owner-2@example.com", learner_name="Owned Learner 2"
    )
    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="standards-intruder@example.com", learner_name="Unrelated Learner"
    )

    response = client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": tagged_subject.subject_id},
    )

    assert response.status_code == 403
