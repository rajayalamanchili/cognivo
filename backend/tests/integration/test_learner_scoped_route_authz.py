"""Integration test: guardian-ownership authorization on the five
learner-scoped GET routes gated by `require_learner_ownership_if_real()`
(services/auth/dependencies.py) -- PR #93's own review flagged this as
shipping with zero regression coverage for the check it exists to add.

Exercises `mastery-state`, `mastery-history`, `recommendations`,
`topic-priority-preview`, and `next-question` with (a) the owning
guardian -> success, (b) a different real guardian -> 403
`not_your_learner`, and (c) no session at all -> 403 `not_your_learner`.
"""

import pytest
from fastapi.testclient import TestClient

from src.models.mastery_state import MasteryState
from tests.integration.quiz_assignment_helpers import (
    login_guardian,
    register_guardian_with_learner,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")

_TOPIC_ID = "integers-and-operations"
_GUARDIAN_A = "authz-guardian-a@example.com"
_GUARDIAN_B = "authz-guardian-b@example.com"


@pytest.fixture()
def client(db_session, monkeypatch):
    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def scenario(client, db_session, algebra_subject):
    """Guardian A owns learner A (with a placement `MasteryState` row so
    `next-question` doesn't 404 for lack of placement data). Guardian B
    is a second, unrelated real guardian -- both logged out on return so
    each test starts from a clean, no-session client."""
    _, learner_a_id = register_guardian_with_learner(
        client, guardian_email=_GUARDIAN_A, learner_name="Learner A"
    )
    db_session.add(
        MasteryState(
            learner_id=learner_a_id,
            subject_id=algebra_subject.subject_id,
            topic_id=_TOPIC_ID,
            p_mastery=0.5,
            update_count=1,
        )
    )
    db_session.commit()
    client.post("/api/auth/logout")

    register_guardian_with_learner(client, guardian_email=_GUARDIAN_B, learner_name="Learner B")
    client.post("/api/auth/logout")

    return {"learner_a_id": learner_a_id}


def _get_routes(learner_id, subject_id):
    return {
        "mastery-state": (f"/api/learners/{learner_id}/mastery-state", {"subject_id": subject_id}),
        "mastery-history": (
            f"/api/learners/{learner_id}/topics/{_TOPIC_ID}/mastery-history",
            {"subject_id": subject_id},
        ),
        "recommendations": (
            f"/api/learners/{learner_id}/recommendations",
            {"subject_id": subject_id},
        ),
        "topic-priority-preview": (
            f"/api/learners/{learner_id}/topic-priority-preview",
            {"subject_id": subject_id},
        ),
    }


_ROUTE_NAMES = list(_get_routes("x", "y"))


@pytest.mark.parametrize("route_name", _ROUTE_NAMES)
def test_owning_guardian_can_read(client, scenario, algebra_subject, route_name):
    login_guardian(client, _GUARDIAN_A)
    path, params = _get_routes(scenario["learner_a_id"], algebra_subject.subject_id)[route_name]
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("route_name", _ROUTE_NAMES)
def test_other_guardian_gets_403(client, scenario, algebra_subject, route_name):
    login_guardian(client, _GUARDIAN_B)
    path, params = _get_routes(scenario["learner_a_id"], algebra_subject.subject_id)[route_name]
    response = client.get(path, params=params)
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


@pytest.mark.parametrize("route_name", _ROUTE_NAMES)
def test_no_session_gets_403(client, scenario, algebra_subject, route_name):
    path, params = _get_routes(scenario["learner_a_id"], algebra_subject.subject_id)[route_name]
    response = client.get(path, params=params)
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


def test_owning_guardian_can_get_next_question(client, scenario, algebra_subject):
    login_guardian(client, _GUARDIAN_A)
    with patch_generation():
        response = client.get(
            f"/api/learners/{scenario['learner_a_id']}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )
    assert response.status_code == 200, response.text


def test_other_guardian_denied_next_question(client, scenario, algebra_subject):
    login_guardian(client, _GUARDIAN_B)
    response = client.get(
        f"/api/learners/{scenario['learner_a_id']}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


def test_no_session_denied_next_question(client, scenario, algebra_subject):
    response = client.get(
        f"/api/learners/{scenario['learner_a_id']}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}
