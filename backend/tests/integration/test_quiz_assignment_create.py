"""Integration test: `POST /api/rosters/{roster_id}/assignments`
(contracts/api.md, T009).

Subset vs. `"all"` targeting, cross-tenant rejection, an
enrolled-after-creation learner not retroactively targeted,
invalid/cross-subject `topic_ids` rejected, and one
`QUIZ_ASSIGNMENT_CREATED` audit event written per targeted learner
(FR-001-FR-005, FR-015; quickstart.md scenarios 1, 7).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""


import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType

pytestmark = pytest.mark.usefixtures("database_available")

_ENTRY_TOPIC = "integers-and-operations"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _register_guardian_with_learner(client, *, guardian_email, learner_name):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": guardian_email, "password": "correct horse"},
    )
    assert register.status_code == 201, register.text
    learner = client.post("/api/learners", json={"display_name": learner_name})
    assert learner.status_code == 201, learner.text
    return learner.json()["learner_id"]


def _join_roster(client, *, learner_id, join_code):
    response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert response.status_code == 201, response.text


def _login_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


@pytest.fixture()
def roster_owner_session(client, algebra_subject):
    _register_instructor(client, "assign-owner-2@example.com")
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster.status_code == 201, roster.text
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    learner_a_id = _register_guardian_with_learner(
        client, guardian_email="assign-guardian-c@example.com", learner_name="Learner C"
    )
    _join_roster(client, learner_id=learner_a_id, join_code=join_code)

    client.post("/api/auth/logout")
    learner_b_id = _register_guardian_with_learner(
        client, guardian_email="assign-guardian-d@example.com", learner_name="Learner D"
    )
    _join_roster(client, learner_id=learner_b_id, join_code=join_code)

    client.post("/api/auth/logout")
    _login_instructor(client, "assign-owner-2@example.com")
    return roster_id, join_code, learner_a_id, learner_b_id


def test_creates_assignment_targeting_a_subset(client, roster_owner_session):
    roster_id, _join_code, learner_a_id, learner_b_id = roster_owner_session

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": [_ENTRY_TOPIC],
            "question_count": 5,
            "learner_ids": [learner_a_id],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["target_learner_ids"] == [learner_a_id]
    assert learner_b_id not in body["target_learner_ids"]


def test_creates_assignment_targeting_all(client, roster_owner_session):
    roster_id, _join_code, learner_a_id, learner_b_id = roster_owner_session

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "learner_ids": "all"},
    )
    assert response.status_code == 201, response.text
    assert set(response.json()["target_learner_ids"]) == {learner_a_id, learner_b_id}


def test_403_on_cross_tenant_roster(client, roster_owner_session):
    roster_id, _join_code, learner_a_id, _learner_b_id = roster_owner_session

    client.post("/api/auth/logout")
    _register_instructor(client, "assign-intruder@example.com")
    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": [_ENTRY_TOPIC],
            "question_count": 5,
            "learner_ids": [learner_a_id],
        },
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_roster_owner"}


def test_enrolled_after_creation_learner_not_retroactively_targeted(
    client, roster_owner_session, algebra_subject
):
    roster_id, join_code, learner_a_id, _learner_b_id = roster_owner_session

    create = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "learner_ids": "all"},
    )
    assert create.status_code == 201, create.text
    targeted_before = set(create.json()["target_learner_ids"])

    client.post("/api/auth/logout")
    late_learner_id = _register_guardian_with_learner(
        client, guardian_email="assign-guardian-late@example.com", learner_name="Late Learner"
    )
    _join_roster(client, learner_id=late_learner_id, join_code=join_code)

    assert late_learner_id not in targeted_before


def test_422_on_empty_target(client, roster_owner_session):
    roster_id, _join_code, _learner_a_id, _learner_b_id = roster_owner_session

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "learner_ids": []},
    )
    assert response.status_code == 422, response.text


def test_404_on_unknown_topic_id(client, roster_owner_session):
    roster_id, _join_code, learner_a_id, _learner_b_id = roster_owner_session

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": ["not-a-real-topic"],
            "question_count": 5,
            "learner_ids": [learner_a_id],
        },
    )
    assert response.status_code == 404, response.text


def test_404_on_cross_subject_topic_id(client, roster_owner_session, biology_subject):
    roster_id, _join_code, learner_a_id, _learner_b_id = roster_owner_session
    biology_topic = next(t.topic_id for t in biology_subject.topics if t.is_entry_level)

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": [biology_topic],
            "question_count": 5,
            "learner_ids": [learner_a_id],
        },
    )
    assert response.status_code == 404, response.text


def test_writes_one_creation_event_per_targeted_learner(client, db_session, roster_owner_session):
    roster_id, _join_code, learner_a_id, learner_b_id = roster_owner_session

    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "learner_ids": "all"},
    )
    assert response.status_code == 201, response.text
    assignment_id = response.json()["assignment_id"]

    db_session.expire_all()
    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.QUIZ_ASSIGNMENT_CREATED)
        .all()
    )
    matching = [e for e in events if e.payload.get("assignment_id") == assignment_id]
    assert {str(e.learner_id) for e in matching} == {learner_a_id, learner_b_id}


def test_list_rosters_assignments(client, roster_owner_session):
    roster_id, _join_code, learner_a_id, _learner_b_id = roster_owner_session

    create = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": [_ENTRY_TOPIC],
            "question_count": 5,
            "learner_ids": [learner_a_id],
        },
    )
    assert create.status_code == 201, create.text
    assignment_id = create.json()["assignment_id"]

    listing = client.get(f"/api/rosters/{roster_id}/assignments")
    assert listing.status_code == 200, listing.text
    ids = {a["assignment_id"] for a in listing.json()["assignments"]}
    assert assignment_id in ids


def test_list_assignments_403_for_non_owner(client, roster_owner_session):
    roster_id, *_rest = roster_owner_session

    client.post("/api/auth/logout")
    _register_instructor(client, "assign-intruder-2@example.com")
    response = client.get(f"/api/rosters/{roster_id}/assignments")
    assert response.status_code == 403, response.text
