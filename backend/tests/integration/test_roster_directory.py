"""Integration tests: the guardian-facing class directory (spec 041
User Story 5) -- `GET /api/rosters/directory` (T040) and the
`is_listed` mutual-exclusion rules enforced via `PATCH /api/rosters/
{roster_id}` (T041).

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


def _set_instructor_display_name(client, display_name="Ms. Rivera"):
    response = client.patch("/api/auth/instructor/me", json={"display_name": display_name})
    assert response.status_code == 200, response.text
    return response.json()


def _register_guardian(client, email="parent@example.com"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["guardian_id"]


def _create_roster(client, subject_id, enrollment_mode="open", grade=None):
    body = {"subject_id": subject_id, "enrollment_mode": enrollment_mode}
    if grade is not None:
        body["grade"] = grade
    response = client.post("/api/rosters", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_directory_is_empty_when_no_roster_is_listed(client):
    _register_guardian(client)
    response = client.get("/api/rosters/directory")
    assert response.status_code == 200
    assert response.json() == {"rosters": []}


def test_listed_open_roster_appears_with_subject_grade_instructor_and_join_code(
    client, algebra_subject
):
    _register_instructor(client)
    _set_instructor_display_name(client, "Ms. Rivera")
    roster = _create_roster(client, algebra_subject.subject_id, "open", grade=7)
    listed = client.patch(f"/api/rosters/{roster['roster_id']}", json={
        "enrollment_mode": "open",
        "is_listed": True,
    })
    assert listed.status_code == 200, listed.text
    assert listed.json()["is_listed"] is True

    client.post("/api/auth/logout")
    _register_guardian(client)

    directory = client.get("/api/rosters/directory")
    assert directory.status_code == 200
    assert directory.json() == {
        "rosters": [
            {
                "roster_id": roster["roster_id"],
                "subject_id": algebra_subject.subject_id,
                "grade": 7,
                "instructor_display_name": "Ms. Rivera",
                "join_code": roster["join_code"],
            }
        ]
    }


def test_closed_roster_never_appears_regardless_of_is_listed(client, algebra_subject):
    _register_instructor(client)
    _set_instructor_display_name(client)
    roster = _create_roster(client, algebra_subject.subject_id, "closed")

    # is_listed=True is itself rejected on a closed roster (T041 below),
    # so there is no way to reach "closed AND is_listed=True" through
    # the API -- this confirms the directory excludes a closed roster
    # on enrollment_mode alone, independent of that other rejection.
    client.post("/api/auth/logout")
    _register_guardian(client)
    directory = client.get("/api/rosters/directory")
    assert directory.json() == {"rosters": []}


def test_unlisted_open_roster_does_not_appear(client, algebra_subject):
    _register_instructor(client)
    _set_instructor_display_name(client)
    _create_roster(client, algebra_subject.subject_id, "open")

    client.post("/api/auth/logout")
    _register_guardian(client)
    directory = client.get("/api/rosters/directory")
    assert directory.json() == {"rosters": []}


def test_setting_is_listed_true_on_a_closed_roster_is_rejected(client, algebra_subject):
    _register_instructor(client)
    _set_instructor_display_name(client)
    roster = _create_roster(client, algebra_subject.subject_id, "closed")

    response = client.patch(
        f"/api/rosters/{roster['roster_id']}",
        json={"enrollment_mode": "closed", "is_listed": True},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "cannot_list_closed_roster"}


def test_setting_is_listed_true_without_a_display_name_is_rejected_for_a_freshly_registered_instructor(
    client, algebra_subject
):
    _register_instructor(client, email="fresh-teacher@example.com")
    roster = _create_roster(client, algebra_subject.subject_id, "open")

    response = client.patch(
        f"/api/rosters/{roster['roster_id']}",
        json={"enrollment_mode": "open", "is_listed": True},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "instructor_display_name_required"}


def test_setting_is_listed_true_without_a_display_name_is_rejected_for_a_pre_existing_instructor(
    client, algebra_subject
):
    """Same rejection, for an instructor account that already existed
    (already created and managed a roster) before ever attempting to
    list one -- no special-casing between a brand-new and a
    pre-existing account (data-model.md's Validation rules)."""
    _register_instructor(client, email="veteran-teacher@example.com")
    roster = _create_roster(client, algebra_subject.subject_id, "open")
    # Some pre-existing activity on the account that isn't setting a
    # display name -- switching the roster's mode back and forth.
    client.patch(f"/api/rosters/{roster['roster_id']}", json={"enrollment_mode": "closed"})
    client.patch(f"/api/rosters/{roster['roster_id']}", json={"enrollment_mode": "open"})

    response = client.patch(
        f"/api/rosters/{roster['roster_id']}",
        json={"enrollment_mode": "open", "is_listed": True},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "instructor_display_name_required"}


def test_closing_while_requesting_listed_is_rejected_without_persisting_the_close(
    client, algebra_subject
):
    """Claude Code Review finding on PR #109: a single PATCH that closes
    an open, listed roster while also asking for is_listed=True must be
    rejected (422) atomically -- the enrollment_mode change must not be
    silently persisted just because it was applied (and committed)
    before the is_listed validation ran."""
    _register_instructor(client)
    _set_instructor_display_name(client)
    roster = _create_roster(client, algebra_subject.subject_id, "open")
    listed = client.patch(
        f"/api/rosters/{roster['roster_id']}", json={"enrollment_mode": "open", "is_listed": True}
    )
    assert listed.json()["is_listed"] is True

    response = client.patch(
        f"/api/rosters/{roster['roster_id']}",
        json={"enrollment_mode": "closed", "is_listed": True},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "cannot_list_closed_roster"}

    rosters = client.get("/api/rosters").json()["rosters"]
    roster_after = next(r for r in rosters if r["roster_id"] == roster["roster_id"])
    assert roster_after["enrollment_mode"] == "open"


def test_closing_a_listed_roster_clears_is_listed_as_a_side_effect(client, algebra_subject):
    _register_instructor(client)
    _set_instructor_display_name(client)
    roster = _create_roster(client, algebra_subject.subject_id, "open")
    listed = client.patch(
        f"/api/rosters/{roster['roster_id']}",
        json={"enrollment_mode": "open", "is_listed": True},
    )
    assert listed.json()["is_listed"] is True

    closed = client.patch(
        f"/api/rosters/{roster['roster_id']}", json={"enrollment_mode": "closed"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["enrollment_mode"] == "closed"
    assert closed.json()["is_listed"] is False

    client.post("/api/auth/logout")
    _register_guardian(client)
    directory = client.get("/api/rosters/directory")
    assert directory.json() == {"rosters": []}
