"""Integration test: a performance-dependent question triggers a real
Recommendation Agent delegation, and a brand-new learner gets an honest
"not enough data" response instead of a fabricated weak area
(spec.md US2, FR-006, `/speckit-analyze` finding M1's structured
`delegation_context` shape), T028.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.tutor_exchange import TutorExchange
from tests.integration.recommendation.scenarios import make_weak_topic
from tests.integration.tutor_helpers import (
    patch_grounded_stream,
    patch_moderation,
    patch_search_passages,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def session_id(client, demo_learner, algebra_subject):
    response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": str(demo_learner.learner_id), "subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def test_performance_question_delegates_to_recommendation_agent(
    client, db_session, demo_learner, algebra_subject, session_id
):
    make_weak_topic(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id="integers-and-operations",
    )

    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(
            ["You should work on Integers and Operations."], grounded_passage_ids=[]
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "what should I work on next?"},
        )
    assert response.status_code == 200, response.text

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.delegation_context, "expected a real Recommendation Agent delegation record"
    delegation = exchange.delegation_context[0]
    assert delegation["agent"] == "recommendation"
    assert delegation["request"] == {
        "learner_id": str(demo_learner.learner_id),
        "subject_id": algebra_subject.subject_id,
    }
    assert delegation["response"]["data_sufficiency"] == "confident"
    weak_topic_ids = {flag["topic_id"] for flag in delegation["response"]["weak_areas"]}
    assert weak_topic_ids == {"integers-and-operations"}


def test_new_learner_gets_honest_insufficient_data_delegation(
    client, db_session, demo_learner, algebra_subject, session_id
):
    # No mastery history seeded at all -- a genuinely brand-new learner.
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(
            ["I don't have enough history yet to say what to work on."],
            grounded_passage_ids=[],
        ),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "what should I work on next?"},
        )
    assert response.status_code == 200, response.text

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.delegation_context
    delegation = exchange.delegation_context[0]
    assert delegation["agent"] == "recommendation"
    assert delegation["response"]["data_sufficiency"] == "insufficient_data"
    assert delegation["response"]["weak_areas"] == []


def test_non_performance_question_does_not_delegate(client, db_session, session_id):
    with (
        patch_moderation(allowed=True),
        patch_search_passages([]),
        patch_grounded_stream(["Light provides the energy."], grounded_passage_ids=[]),
    ):
        response = client.post(
            f"/api/tutor/sessions/{session_id}/messages",
            json={"question": "why does photosynthesis need light?"},
        )
    assert response.status_code == 200, response.text

    exchange = db_session.query(TutorExchange).filter(TutorExchange.session_id == session_id).one()
    assert exchange.delegation_context == []
