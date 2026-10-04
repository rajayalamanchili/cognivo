"""Integration test: the instructor roster dashboard's roster-wide
`standards_summary` aggregate (spec 038 FR-005, User Story 2).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.mastery_state import MasteryState
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import validate_content_artifact
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
            "subject_id": "dashboard-standards-summary-test-subject",
            "display_name": "Dashboard Standards Summary Test Subject",
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


def _enroll(client, db_session, *, join_code, email, display_name, p_mastery, subject_id):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email=email, learner_name=display_name
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)
    if p_mastery is not None:
        db_session.add(
            MasteryState(
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id="topic-a",
                p_mastery=p_mastery,
                consecutive_mastered_observations=2 if p_mastery >= 0.7 else 0,
            )
        )
        db_session.commit()
    client.post("/api/auth/logout")
    return learner_id


def test_standards_summary_counts_met_learners_out_of_roster_total(client, db_session, tagged_subject):
    register_instructor(client, "standards-summary-teacher@example.com")
    roster = client.post(
        "/api/rosters",
        json={"subject_id": tagged_subject.subject_id, "enrollment_mode": "open"},
    )
    assert roster.status_code == 201, roster.text
    roster_id, join_code = roster.json()["roster_id"], roster.json()["join_code"]
    client.post("/api/auth/logout")

    _enroll(
        client, db_session, join_code=join_code,
        email="standards-summary-parent-1@example.com", display_name="Learner One",
        p_mastery=0.9, subject_id=tagged_subject.subject_id,
    )
    _enroll(
        client, db_session, join_code=join_code,
        email="standards-summary-parent-2@example.com", display_name="Learner Two",
        p_mastery=0.3, subject_id=tagged_subject.subject_id,
    )

    login_instructor(client, "standards-summary-teacher@example.com")
    response = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert response.status_code == 200, response.text

    [summary] = response.json()["standards_summary"]
    assert summary["framework"] == _STANDARD["framework"]
    assert summary["code"] == _STANDARD["code"]
    assert summary["title"] == _STANDARD["title"]
    assert summary["met_count"] == 1
    assert summary["total_count"] == 2


def test_standards_summary_empty_for_subject_with_zero_tags(client, db_session, algebra_subject):
    register_instructor(client, "standards-summary-teacher-2@example.com")
    roster = client.post(
        "/api/rosters",
        json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"},
    )
    assert roster.status_code == 201, roster.text
    roster_id = roster.json()["roster_id"]

    response = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert response.status_code == 200, response.text
    assert response.json()["standards_summary"] == []
