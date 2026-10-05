"""Integration test: `POST /api/rosters`'s optional `grade` field is
validated against the chosen subject's own `GradeBand` rows at creation
time (spec 040 FR-009, found during `/speckit-implement`; research.md
Decision 6; tasks.md T011).
"""

import pytest

from tests.integration.quiz_assignment_helpers import login_instructor, register_instructor

pytestmark = pytest.mark.usefixtures("database_available")

_INSTRUCTOR_EMAIL = "roster-grade-instructor@example.com"


def _client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_mismatched_grade_rejected(physics_subject, monkeypatch):
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    response = client.post(
        "/api/rosters",
        json={"subject_id": "physics", "enrollment_mode": "open", "grade": 8},
    )
    assert response.status_code == 422, response.text


def test_matching_grade_accepted(physics_subject, monkeypatch):
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    response = client.post(
        "/api/rosters",
        json={"subject_id": "physics", "enrollment_mode": "open", "grade": 9},
    )
    assert response.status_code == 201, response.text
    assert response.json()["grade"] == 9


def test_overlapping_grade_accepted_for_both_subjects_independently(
    algebra_2_subject, physics_subject, monkeypatch
):
    """spec 040 Edge Cases: algebra-2 (9-10) and physics (9-10,11)
    overlap at grades 9-10 -- FR-009 validates each roster against its
    own subject only, never comparing subjects against each other, so
    both remain independently creatable at the same declared grade."""
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    algebra_2_response = client.post(
        "/api/rosters",
        json={"subject_id": "algebra-2", "enrollment_mode": "open", "grade": 10},
    )
    assert algebra_2_response.status_code == 201, algebra_2_response.text

    physics_response = client.post(
        "/api/rosters",
        json={"subject_id": "physics", "enrollment_mode": "open", "grade": 10},
    )
    assert physics_response.status_code == 201, physics_response.text


def test_out_of_range_grade_rejected_422_even_for_ungraded_subject(biology_subject, monkeypatch):
    """PR #105 review finding: an ungraded subject (no GradeBand rows)
    makes `_check_grade_matches_subject` a no-op, so an out-of-range
    `grade` would otherwise reach the DB and trip
    `ck_classroom_rosters_grade_range` as an unhandled 500 instead of a
    clean 422. `CreateRosterIn.grade`'s `ge=1, le=12` constraint catches
    this at the API boundary, before any subject-specific check runs."""
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    response = client.post(
        "/api/rosters",
        json={"subject_id": "biology", "enrollment_mode": "open", "grade": 99},
    )
    assert response.status_code == 422, response.text


def test_ungraded_subject_accepts_any_declared_grade(biology_subject, monkeypatch):
    """research.md Decision 6 / FR-009: an ungraded subject (zero
    GradeBand rows) imposes no restriction, mirroring grade_bands'
    opt-in-per-subject precedent."""
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    response = client.post(
        "/api/rosters",
        json={"subject_id": "biology", "enrollment_mode": "open", "grade": 3},
    )
    assert response.status_code == 201, response.text
    assert response.json()["grade"] == 3


def test_no_grade_declared_is_unrestricted(physics_subject, monkeypatch):
    """Omitting `grade` entirely preserves today's exact behavior --
    no roster created before this feature is retroactively affected."""
    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL)
    login_instructor(client, _INSTRUCTOR_EMAIL)

    response = client.post(
        "/api/rosters", json={"subject_id": "physics", "enrollment_mode": "open"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["grade"] is None
