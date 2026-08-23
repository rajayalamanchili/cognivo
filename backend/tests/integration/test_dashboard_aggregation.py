"""Integration test: dashboard's per-learner data is byte-for-byte
identical to calling that learner's own recommendations endpoint
directly (quickstart scenario 6, SC-001, T036).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.recommendation.scenarios import make_in_progress_topic, make_weak_topic

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email="teacher@example.com"):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _register_guardian_with_learner(client, email="parent@example.com", display_name="Jamie"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def test_dashboard_entry_matches_direct_recommendations_call(client, db_session, algebra_subject):
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster.status_code == 201, roster.text
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )
    make_in_progress_topic(
        db_session,
        learner_id=learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id="variables-and-expressions",
        p_mastery=0.5,
    )

    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    direct = client.get(
        f"/api/learners/{learner_id}/recommendations",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert direct.status_code == 200, direct.text

    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": "teacher@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200

    dashboard = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    dashboard_body = dashboard.json()
    assert dashboard_body["roster_id"] == roster_id
    assert dashboard_body["subject_id"] == algebra_subject.subject_id
    assert len(dashboard_body["learners"]) == 1

    entry = dashboard_body["learners"][0]
    assert entry["learner_id"] == learner_id
    assert entry["display_name"] == "Jamie"
    assert entry["recommendations"] == direct.json()
