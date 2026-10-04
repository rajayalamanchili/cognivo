"""Integration test: the instructor roster dashboard's per-learner
`standards` field matches `compute_standards_coverage`'s own output
exactly, scoped by the existing roster-ownership check (spec 038 FR-004,
FR-007).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.mastery_state import MasteryState
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import validate_content_artifact
from src.services.standards.coverage import compute_standards_coverage
from tests.integration.quiz_assignment_helpers import (
    join_roster,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
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
            "subject_id": "dashboard-standards-test-subject",
            "display_name": "Dashboard Standards Test Subject",
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


def test_dashboard_learner_standards_matches_coverage_function(
    client, db_session, tagged_subject
):
    register_instructor(client, "standards-dashboard-teacher@example.com")
    roster = client.post(
        "/api/rosters",
        json={"subject_id": tagged_subject.subject_id, "enrollment_mode": "open"},
    )
    assert roster.status_code == 201, roster.text
    roster_id, join_code = roster.json()["roster_id"], roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="standards-dashboard-parent@example.com",
        learner_name="Dashboard Learner",
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

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

    client.post("/api/auth/logout")
    login_instructor(client, "standards-dashboard-teacher@example.com")

    response = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert response.status_code == 200, response.text
    [learner_entry] = response.json()["learners"]
    assert str(learner_id) == learner_entry["learner_id"]

    expected = compute_standards_coverage(
        db_session, learner_id=learner_id, subject_id=tagged_subject.subject_id
    )
    assert learner_entry["standards"] == [
        {
            "framework": e.framework,
            "code": e.code,
            "title": e.title,
            "topic_ids": list(e.topic_ids),
            "status": e.status,
        }
        for e in expected
    ]
    assert learner_entry["standards"][0]["status"] == "met"
