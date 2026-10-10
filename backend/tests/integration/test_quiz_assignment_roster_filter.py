"""Integration test: `GET /api/learners/{learner_id}/assignments`'s
optional `roster_id` filter -- spec 044 FR-002/research.md §3. Added so
Guardian · My learners' per-subject tabs (spec 044 Story 1) don't mix
every enrollment's assignments together on each tab.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.quiz_assignment_helpers import (
    create_assignment,
    create_roster,
    join_roster,
    login_guardian,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_roster_id_filters_to_only_that_rosters_assignments(client, algebra_subject):
    teacher_email = "roster-filter-teacher@example.com"
    guardian_email = "roster-filter-parent@example.com"
    register_instructor(client, teacher_email)
    roster_a, join_code_a = create_roster(client, subject_id=algebra_subject.subject_id)
    roster_b, join_code_b = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code_a)
    join_roster(client, learner_id=learner_id, join_code=join_code_b)

    client.post("/api/auth/logout")
    login_instructor(client, teacher_email)
    assignment_a = create_assignment(client, roster_id=roster_a)
    assignment_b = create_assignment(client, roster_id=roster_b)

    client.post("/api/auth/logout")
    login_guardian(client, guardian_email)
    response = client.get(f"/api/learners/{learner_id}/assignments", params={"roster_id": roster_a})

    assert response.status_code == 200, response.text
    [entry] = response.json()["assignments"]
    assert entry["assignment_id"] == assignment_a["assignment_id"]
    assert entry["assignment_id"] != assignment_b["assignment_id"]


def test_omitting_roster_id_returns_every_assignment(client, algebra_subject):
    teacher_email = "roster-filter-teacher-2@example.com"
    guardian_email = "roster-filter-parent-2@example.com"
    register_instructor(client, teacher_email)
    roster_a, join_code_a = create_roster(client, subject_id=algebra_subject.subject_id)
    roster_b, join_code_b = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code_a)
    join_roster(client, learner_id=learner_id, join_code=join_code_b)

    client.post("/api/auth/logout")
    login_instructor(client, teacher_email)
    create_assignment(client, roster_id=roster_a)
    create_assignment(client, roster_id=roster_b)

    client.post("/api/auth/logout")
    login_guardian(client, guardian_email)
    response = client.get(f"/api/learners/{learner_id}/assignments")

    assert response.status_code == 200, response.text
    assert len(response.json()["assignments"]) == 2
