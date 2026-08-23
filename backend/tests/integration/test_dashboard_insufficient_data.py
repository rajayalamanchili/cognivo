"""Integration test: a learner with insufficient assessment history is
shown with an explicit indicator, never omitted or as an error
(FR-009, T037).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

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


def test_learner_with_no_history_shown_with_insufficient_data_indicator(client, algebra_subject):
    """A brand-new learner (zero assessment events at all) has no
    `MasteryState` rows, so `classify_topics` reaches
    `confidently_assessed_count == 0` and reports
    `data_sufficiency: "insufficient_data"` -- this must appear as a
    normal 200 dashboard entry, not an error and not a missing learner
    (FR-009)."""
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": "teacher@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200

    dashboard = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    learners = dashboard.json()["learners"]
    assert len(learners) == 1

    entry = learners[0]
    assert entry["learner_id"] == learner_id
    assert entry["recommendations"]["data_sufficiency"] == "insufficient_data"
    assert entry["recommendations"]["weak_areas"] == []
