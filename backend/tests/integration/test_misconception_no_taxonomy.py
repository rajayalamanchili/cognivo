"""Integration test: a subject with no `misconceptions` taxonomy
authored for a flagged topic produces a full weak-area report with
`misconception: null` on that flag and no error (spec.md edge case),
T025.
"""

import pytest
from fastapi.testclient import TestClient

from tests.integration.recommendation.scenarios import make_weak_topic


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_topic_with_no_taxonomy_yields_null_misconception_and_no_error(
    client, db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id
    # integers-and-operations has no `misconceptions` list authored.
    topic_id = "integers-and-operations"

    make_weak_topic(db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id)

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    flags = [f for f in body["weak_areas"] if f["topic_id"] == topic_id]
    assert len(flags) == 1
    assert flags[0]["misconception"] is None
