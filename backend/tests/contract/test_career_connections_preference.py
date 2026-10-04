"""Contract test: `GET`/`PATCH /api/learners/{id}/career-connections-
preference` (spec 039 FR-004/FR-005/FR-008). A demo (or nonexistent)
`learner_id` round-trips with no session required; a real learner's
preference requires the owning guardian's session (`401` with no
session, `403` for a non-owning guardian); an unset real learner's `GET`
returns the column default; two distinct real learners owned by the same
guardian have independent preference values.

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import pytest

from tests.integration.quiz_assignment_helpers import register_guardian_with_learner

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_demo_learner_round_trips_with_no_session(client, demo_learner):
    get_response = client.get(
        f"/api/learners/{demo_learner.learner_id}/career-connections-preference"
    )
    assert get_response.status_code == 200
    assert get_response.json() == {"enabled": True}

    patch_response = client.patch(
        f"/api/learners/{demo_learner.learner_id}/career-connections-preference",
        json={"enabled": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json() == {"enabled": False}

    get_again = client.get(
        f"/api/learners/{demo_learner.learner_id}/career-connections-preference"
    )
    assert get_again.json() == {"enabled": False}


def test_real_learner_unset_preference_defaults_true(client):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-pref-owner@example.com", learner_name="Owned Learner"
    )

    response = client.get(f"/api/learners/{learner_id}/career-connections-preference")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_real_learner_requires_session(client):
    """No session at all maps to the same 403 `require_learner_
    ownership_if_real()` already raises for a wrong-guardian session --
    it never distinguishes the two with a 401 (matches every other
    learner-scoped route's existing contract)."""
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-pref-nosession@example.com", learner_name="Owned Learner"
    )
    client.post("/api/auth/logout")

    response = client.get(f"/api/learners/{learner_id}/career-connections-preference")

    assert response.status_code == 403


def test_non_owning_guardian_cannot_read_or_write(client):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-pref-owner2@example.com", learner_name="Owned Learner 2"
    )
    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="career-pref-intruder@example.com", learner_name="Unrelated Learner"
    )

    get_response = client.get(f"/api/learners/{learner_id}/career-connections-preference")
    patch_response = client.patch(
        f"/api/learners/{learner_id}/career-connections-preference", json={"enabled": False}
    )

    assert get_response.status_code == 403
    assert patch_response.status_code == 403


def test_owning_guardian_can_write_and_it_persists(client):
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="career-pref-writer@example.com", learner_name="Owned Learner"
    )

    patch_response = client.patch(
        f"/api/learners/{learner_id}/career-connections-preference", json={"enabled": False}
    )
    get_response = client.get(f"/api/learners/{learner_id}/career-connections-preference")

    assert patch_response.status_code == 200
    assert patch_response.json() == {"enabled": False}
    assert get_response.json() == {"enabled": False}


def test_two_real_learners_have_independent_preferences(client):
    """Edge Cases: a guardian managing more than one real learner can set
    this preference independently per learner -- turning it off for one
    does not affect another."""
    guardian_response = client.post(
        "/api/auth/guardian/register",
        json={"email": "career-pref-multi@example.com", "password": "correct horse"},
    )
    assert guardian_response.status_code == 201
    first = client.post("/api/learners", json={"display_name": "First Learner"})
    second = client.post("/api/learners", json={"display_name": "Second Learner"})
    first_id = first.json()["learner_id"]
    second_id = second.json()["learner_id"]

    client.patch(
        f"/api/learners/{first_id}/career-connections-preference", json={"enabled": False}
    )

    first_get = client.get(f"/api/learners/{first_id}/career-connections-preference")
    second_get = client.get(f"/api/learners/{second_id}/career-connections-preference")

    assert first_get.json() == {"enabled": False}
    assert second_get.json() == {"enabled": True}
