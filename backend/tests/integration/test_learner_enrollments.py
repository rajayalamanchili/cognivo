"""Integration test: `GET /api/learners/{learner_id}/enrollments` --
added while wiring spec 038's guardian-facing standards view (T014),
not in the original contracts/api-changes.md.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.grade_progress import GradeProgress
from tests.integration.quiz_assignment_helpers import (
    create_roster,
    join_roster,
    register_guardian_with_learner,
    register_instructor,
    seed_and_login_default_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_lists_the_learners_enrolled_rosters_subject(client, algebra_subject):
    register_instructor(client, "learner-enrollments-teacher@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="learner-enrollments-parent@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    response = client.get(f"/api/learners/{learner_id}/enrollments")

    assert response.status_code == 200, response.text
    [entry] = response.json()["enrollments"]
    assert entry["roster_id"] == roster_id
    assert entry["subject_id"] == algebra_subject.subject_id
    assert entry["is_default_instructor_roster"] is False


def test_is_default_instructor_roster_true_only_for_the_default_instructors_roster(
    client, algebra_subject, db_session, monkeypatch
):
    """spec 043 contracts/api-changes.md §5, T022."""
    default_email = "learner-enrollments-default-teacher@example.com"
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", default_email)

    seed_and_login_default_instructor(client, db_session, default_email)
    default_roster_id, default_join_code = create_roster(
        client, subject_id=algebra_subject.subject_id
    )

    client.post("/api/auth/logout")
    register_instructor(client, "learner-enrollments-real-teacher@example.com")
    real_roster_id, real_join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-default-parent@example.com",
        learner_name="Learner",
    )
    join_roster(client, learner_id=learner_id, join_code=default_join_code)
    join_roster(client, learner_id=learner_id, join_code=real_join_code)

    response = client.get(f"/api/learners/{learner_id}/enrollments")

    assert response.status_code == 200, response.text
    by_roster_id = {entry["roster_id"]: entry for entry in response.json()["enrollments"]}
    assert by_roster_id[default_roster_id]["is_default_instructor_roster"] is True
    assert by_roster_id[real_roster_id]["is_default_instructor_roster"] is False


def test_non_owning_guardian_gets_403(client, algebra_subject):
    register_instructor(client, "learner-enrollments-teacher-2@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-parent-2@example.com",
        learner_name="Owned Learner",
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-intruder@example.com",
        learner_name="Unrelated Learner",
    )

    response = client.get(f"/api/learners/{learner_id}/enrollments")
    assert response.status_code == 403


def test_has_starting_grade_false_until_a_grade_progress_row_exists(
    client, algebra_subject, db_session
):
    """spec 044 FR-024, US5: agrees with `_assign_starting_grade_if_graded`'s
    own `GradeProgress`-existence guard (no drift between the two checks)."""
    register_instructor(client, "learner-enrollments-placement-teacher@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-placement-parent@example.com",
        learner_name="Learner",
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    response = client.get(f"/api/learners/{learner_id}/enrollments")
    assert response.status_code == 200, response.text
    [entry] = response.json()["enrollments"]
    assert entry["has_starting_grade"] is False

    db_session.add(
        GradeProgress(
            learner_id=learner_id, subject_id=algebra_subject.subject_id, unlocked_grade=6
        )
    )
    db_session.commit()

    response = client.get(f"/api/learners/{learner_id}/enrollments")
    assert response.status_code == 200, response.text
    [entry] = response.json()["enrollments"]
    assert entry["has_starting_grade"] is True


def test_has_starting_grade_true_for_an_ungraded_subject(client, biology_subject):
    """spec 044 FR-024: an ungraded subject (zero declared `GradeBand`
    rows) never offers "Take placement" -- `has_starting_grade` is true
    here even with no `GradeProgress` row, same as
    `_assign_starting_grade_if_graded`'s own ungraded early return."""
    register_instructor(client, "learner-enrollments-ungraded-teacher@example.com")
    roster_id, join_code = create_roster(client, subject_id=biology_subject.subject_id)

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-ungraded-parent@example.com",
        learner_name="Learner",
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    response = client.get(f"/api/learners/{learner_id}/enrollments")
    assert response.status_code == 200, response.text
    [entry] = response.json()["enrollments"]
    assert entry["has_starting_grade"] is True


def test_empty_list_for_a_learner_with_no_enrollments(client):
    _, learner_id = register_guardian_with_learner(
        client,
        guardian_email="learner-enrollments-no-rosters@example.com",
        learner_name="Unenrolled Learner",
    )

    response = client.get(f"/api/learners/{learner_id}/enrollments")

    assert response.status_code == 200, response.text
    assert response.json()["enrollments"] == []
