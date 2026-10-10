"""Contract tests: `POST /api/practice-sessions` (spec 022 FR-001,
FR-006, FR-008, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.mastery_state import MasteryState
from src.models.practice_session import PracticeSession
from tests.integration.quiz_assignment_helpers import (
    login_guardian,
    register_guardian_with_learner,
)
from tests.integration.quiz_helpers import patch_generation


def _complete_placement(client: TestClient, subject_id: str) -> str:
    with patch_generation():
        start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text
    return start.json()["placement_session_id"]


def test_valid_start_returns_session_and_first_question(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["expires_at"] is not None
    assert body["question"] is not None

    session = db_session.get(PracticeSession, body["practice_session_id"])
    assert session.time_limit_seconds == 1800
    assert session.subject_id == algebra_subject.subject_id


def test_unknown_subject_returns_404(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={
            "subject_id": "not-a-real-subject",
            "time_limit_seconds": 1800,
        },
    )
    assert start.status_code == 404, start.text


def test_missing_time_limit_returns_422(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={"subject_id": algebra_subject.subject_id},
    )
    assert start.status_code == 422, start.text


def test_invalid_time_limit_returns_422(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={
            "subject_id": algebra_subject.subject_id,
            "time_limit_seconds": 42,
        },
    )
    assert start.status_code == 422, start.text


def test_request_schema_has_no_client_elapsed_time_field(
    db_session, demo_learner, algebra_subject
):
    """FR-006: extra fields (e.g. a client-asserted expires_at) are
    ignored -- the server derives expires_at from its own started_at."""
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )
    assert start.status_code == 200, start.text
    assert start.json()["expires_at"] != "2099-01-01T00:00:00Z"


def test_omitted_learner_id_still_resolves_the_demo_learner(
    db_session, demo_learner, algebra_subject
):
    """Unchanged pre-spec-044 behavior: omitting learner_id entirely
    keeps today's demo-learner-only path."""
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text

    session = db_session.get(PracticeSession, start.json()["practice_session_id"])
    assert session.learner_id == demo_learner.learner_id


def test_nonexistent_learner_id_404s_instead_of_falling_back_to_demo(
    db_session, demo_learner, algebra_subject
):
    """spec 044 FR-008: a supplied learner_id is now honored (gated by
    ownership), not silently ignored -- a nonexistent id has no
    placement data, so it 404s rather than silently becoming the demo
    learner's own session."""
    from src.api.main import app

    client = TestClient(app)

    start = client.post(
        "/api/practice-sessions",
        json={
            "learner_id": "00000000-0000-0000-0000-000000000000",
            "subject_id": algebra_subject.subject_id,
            "time_limit_seconds": 1800,
        },
    )
    assert start.status_code == 404, start.text


def test_real_learner_with_mastery_state_can_start_a_session(
    db_session, algebra_subject, monkeypatch
):
    """spec 044 FR-008, US2: the guardian's own real learner can start a
    timed session directly, same as the demo learner."""
    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    client = TestClient(app, base_url="https://testserver")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="practice-start-owner@example.com", learner_name="Real Learner"
    )
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id="integers-and-operations",
            p_mastery=0.5,
            update_count=1,
        )
    )
    db_session.commit()

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": learner_id,
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text

    session = db_session.get(PracticeSession, start.json()["practice_session_id"])
    assert str(session.learner_id) == learner_id


def test_real_learner_with_no_placement_data_can_still_start_a_session(
    db_session, algebra_subject, monkeypatch
):
    """spec 044 FR-008/research.md §1: mirrors get_next_question's exact
    bypass -- a real learner who has never answered a question yet
    (zero MasteryState rows) must not 404 on their very first use of
    this shortcut."""
    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    client = TestClient(app, base_url="https://testserver")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="practice-start-fresh@example.com", learner_name="Fresh Learner"
    )
    assert (
        db_session.query(MasteryState).filter(MasteryState.learner_id == learner_id).first()
        is None
    )

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": learner_id,
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text


def test_other_guardians_learner_id_is_forbidden(db_session, algebra_subject, monkeypatch):
    """spec 044 FR-008: a guardian must not be able to start a timed
    session for a learner they don't own, by supplying that learner's
    id directly."""
    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    client = TestClient(app, base_url="https://testserver")
    _, owner_learner_id = register_guardian_with_learner(
        client, guardian_email="practice-start-owner-b@example.com", learner_name="Owned"
    )
    db_session.add(
        MasteryState(
            learner_id=owner_learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id="integers-and-operations",
            p_mastery=0.5,
            update_count=1,
        )
    )
    db_session.commit()
    client.post("/api/auth/logout")

    register_guardian_with_learner(
        client, guardian_email="practice-start-intruder@example.com", learner_name="Other"
    )
    login_guardian(client, "practice-start-intruder@example.com")

    start = client.post(
        "/api/practice-sessions",
        json={
            "learner_id": owner_learner_id,
            "subject_id": algebra_subject.subject_id,
            "time_limit_seconds": 1800,
        },
    )
    assert start.status_code == 403, start.text
    assert start.json() == {"detail": "not_your_learner"}
