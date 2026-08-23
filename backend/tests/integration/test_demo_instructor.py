"""Integration test: `GET /api/demo-instructor` requires no session
cookie and resolves to the seeded `DemoInstructorProfile` with
`is_demo: true` (quickstart scenario 10, T049).

Also covers the `/speckit-clarify`-approved extension beyond the
literal contract: the response also issues a session cookie, so the
demo instructor is actually navigable (not identity-only) across
`/api/rosters`, `/api/rosters/{roster_id}/dashboard`, and
`/api/content-review/flagged` -- including creating a roster, which
requires `classroom_rosters.instructor_id` no longer being a hard FK
to `real_instructor_accounts` (migration `7e686faa5e6d`).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from scripts.seed_demo_instructor import seed_demo_instructor
from src.models.demo_instructor_profile import DemoInstructorProfile
from src.services.auth.tokens import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_demo_instructor_reachable_without_any_auth_route(client, db_session):
    seeded = seed_demo_instructor()

    response = client.get("/api/demo-instructor")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["instructor_id"] == str(seeded.instructor_id)
    assert body["display_name"] == seeded.display_name

    db_session.expire_all()
    row = db_session.get(DemoInstructorProfile, uuid.UUID(body["instructor_id"]))
    assert row is not None
    assert row.is_demo is True


def test_demo_instructor_session_can_browse_and_create_a_roster(
    client, db_session, algebra_subject
):
    seed_demo_instructor()

    response = client.get("/api/demo-instructor")
    assert response.status_code == 200, response.text
    assert SESSION_COOKIE_NAME in client.cookies

    empty = client.get("/api/rosters")
    assert empty.status_code == 200
    assert empty.json() == {"rosters": []}

    created = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert created.status_code == 201, created.text
    roster_id = created.json()["roster_id"]

    dashboard = client.get(f"/api/rosters/{roster_id}/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["learners"] == []

    flagged = client.get("/api/content-review/flagged")
    assert flagged.status_code == 200
    assert flagged.json() == {"flagged": []}
