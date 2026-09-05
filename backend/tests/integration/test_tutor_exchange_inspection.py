"""Integration test: `GET /api/tutor/exchanges/{exchange_id}` -- auth
(owning guardian, enrolled instructor, demo-instructor), the derived
`status` field, and the structured `delegation_context`/
`retrieved_passages` payload shape (spec.md US3, contracts/api.md),
T031.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from scripts.seed_demo_instructor import seed_demo_instructor
from src.models.content_passage_embedding import EMBEDDING_DIMENSION, ContentPassageEmbedding
from src.models.tutor_exchange import TutorExchange
from tests.integration.quiz_assignment_helpers import (
    create_roster,
    join_roster,
    login_guardian,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.tutor_helpers import (
    make_passage,
    patch_grounded_stream,
    patch_moderation,
    patch_search_passages,
    patch_shielding_match,
    seed_open_question,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def scenario(client, biology_subject):
    """Instructor A owns a roster (biology) with learner A (guardian A)
    enrolled. Returns ids and leaves no one logged in."""
    register_instructor(client, "exchange-inspect-instructor-a@example.com")
    roster_id, join_code = create_roster(client, subject_id=biology_subject.subject_id)

    client.post("/api/auth/logout")
    guardian_a_id, learner_a_id = register_guardian_with_learner(
        client, guardian_email="exchange-inspect-guardian-a@example.com", learner_name="Learner A"
    )
    join_roster(client, learner_id=learner_a_id, join_code=join_code)

    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="exchange-inspect-guardian-b@example.com", learner_name="Learner B"
    )

    client.post("/api/auth/logout")
    register_instructor(client, "exchange-inspect-instructor-b@example.com")

    client.post("/api/auth/logout")
    return {
        "roster_id": roster_id,
        "guardian_a_id": guardian_a_id,
        "learner_a_id": learner_a_id,
    }


@pytest.fixture()
def exchange(client, db_session, biology_subject, scenario):
    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    open_response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": scenario["learner_a_id"], "subject_id": biology_subject.subject_id},
    )
    assert open_response.status_code == 201, open_response.text
    session_id = open_response.json()["session_id"]

    passage = make_passage(topic_id="photosynthesis", text="Light drives photosynthesis.")
    # A real row, not just the mocked search_passages() return value --
    # the inspection route's retrieved_passages join queries the actual
    # table, so this must genuinely exist for it to find anything.
    db_session.add(
        ContentPassageEmbedding(
            passage_id=passage.passage_id,
            subject_id=biology_subject.subject_id,
            topic_id=passage.topic_id,
            field=passage.field,
            text=passage.text,
            embedding=[0.0] * EMBEDDING_DIMENSION,
            content_version=biology_subject.content_version,
        )
    )
    db_session.commit()
    with (
        patch_moderation(allowed=True),
        patch_search_passages([passage]),
        patch_grounded_stream(
            ["Light provides energy."], grounded_passage_ids=[passage.passage_id]
        ),
    ):
        message_response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "why does photosynthesis need light?"},
        )
    assert message_response.status_code == 200, message_response.text

    exchange_row = (
        db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    )
    client.post("/api/auth/logout")
    return {"exchange_id": str(exchange_row.exchange_id), "passage": passage}


def test_owning_guardian_can_inspect(client, exchange):
    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["answer_text"] == "Light provides energy."
    assert body["grounded"] is True
    assert body["question_text"] == "why does photosynthesis need light?"
    assert body["retrieved_passages"] == [
        {
            "passage_id": str(exchange["passage"].passage_id),
            "topic_id": "photosynthesis",
            "field": "skill_summary",
            "text": "Light drives photosynthesis.",
        }
    ]
    assert body["delegation_context"] == []
    assert body["shielded"] is False
    assert body["shielded_question_id"] is None


def test_shielded_exchange_is_inspectable(client, db_session, biology_subject, scenario):
    """spec 016 FR-007/SC-003: a shielded exchange's trigger question is
    inspectable via this same endpoint, without asking the Tutor Agent
    itself to explain."""
    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    learner_a_id = scenario["learner_a_id"]
    open_question = seed_open_question(
        db_session, learner_id=uuid.UUID(learner_a_id), subject=biology_subject
    )
    open_response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_a_id, "subject_id": biology_subject.subject_id},
    )
    session_id = open_response.json()["session_id"]

    with (
        patch_moderation(allowed=True),
        patch_shielding_match(matches=True),
        patch_search_passages([]),
        patch_grounded_stream(["Think it through first."], grounded_passage_ids=[]),
    ):
        message_response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "just give me the answer"},
        )
    assert message_response.status_code == 200, message_response.text

    exchange_row = (
        db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    )
    response = client.get(f"/api/tutor/exchanges/{exchange_row.exchange_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["shielded"] is True
    assert body["shielded_question_id"] == str(open_question.question_id)


def test_other_guardian_forbidden(client, exchange):
    login_guardian(client, "exchange-inspect-guardian-b@example.com")
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


def test_enrolled_instructor_can_inspect(client, exchange):
    login_instructor(client, "exchange-inspect-instructor-a@example.com")
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


def test_unrelated_instructor_forbidden(client, exchange):
    login_instructor(client, "exchange-inspect-instructor-b@example.com")
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_learner_instructor"}


def test_no_session_forbidden(client, exchange):
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_authorized"}


def test_demo_instructor_with_enrollment_can_inspect(
    client, db_session, biology_subject, scenario, exchange
):
    seed_demo_instructor()
    demo_login = client.get("/api/demo-instructor")
    assert demo_login.status_code == 200, demo_login.text

    created = client.post(
        "/api/rosters", json={"subject_id": biology_subject.subject_id, "enrollment_mode": "open"}
    )
    assert created.status_code == 201, created.text
    join_code = created.json()["join_code"]
    client.post("/api/auth/logout")

    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    joined = client.post(
        "/api/rosters/join",
        json={"learner_id": scenario["learner_a_id"], "join_code": join_code},
    )
    assert joined.status_code == 201, joined.text
    client.post("/api/auth/logout")

    client.get("/api/demo-instructor")
    response = client.get(f"/api/tutor/exchanges/{exchange['exchange_id']}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


def test_derived_status_is_in_progress_before_completion(
    client, db_session, scenario, biology_subject
):
    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    open_response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": scenario["learner_a_id"], "subject_id": biology_subject.subject_id},
    )
    session_id = open_response.json()["session_id"]

    in_flight = TutorExchange(session_id=session_id, question_text="still going")
    db_session.add(in_flight)
    db_session.commit()

    response = client.get(f"/api/tutor/exchanges/{in_flight.exchange_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"


def test_derived_status_is_failed_after_failed_at(client, db_session, scenario, biology_subject):
    login_guardian(client, "exchange-inspect-guardian-a@example.com")
    open_response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": scenario["learner_a_id"], "subject_id": biology_subject.subject_id},
    )
    session_id = open_response.json()["session_id"]

    import datetime

    failed = TutorExchange(
        session_id=session_id,
        question_text="it broke",
        failed_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(failed)
    db_session.commit()

    response = client.get(f"/api/tutor/exchanges/{failed.exchange_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
