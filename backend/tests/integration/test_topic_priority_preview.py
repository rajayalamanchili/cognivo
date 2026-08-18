"""Integration test: `GET /api/learners/{learner_id}/topic-priority-preview`
(contracts/api.md, research.md §1/§3), T018.

`next_topic` is always present, `upcoming_topics` is capped at 3, and a
404 is raised for an unknown/unvalidated `subject_id` (matching
`mastery.py`/`recommendation.py`'s existing gate). This is a pure,
read-only preview: it must write zero `AssessmentEvent` rows and emit
zero Langfuse spans -- verified here by patching `flush_traces` (the
choke point every `traced_request()` call goes through) and asserting
it is never invoked, rather than wrapping this call in one.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.mastery_state import MasteryState


def test_next_topic_always_present_and_upcoming_capped_at_three(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
        params={"subject_id": algebra_subject.subject_id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject_id"] == algebra_subject.subject_id
    assert body["next_topic"]["topic_id"]
    assert len(body["upcoming_topics"]) <= 3
    assert isinstance(body["is_fallback"], bool)


def test_upcoming_topics_excludes_next_topic_itself(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
        params={"subject_id": algebra_subject.subject_id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    upcoming_ids = {entry["topic_id"] for entry in body["upcoming_topics"]}
    assert body["next_topic"]["topic_id"] not in upcoming_ids


def test_404_for_unknown_subject_id(db_session, demo_learner):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
        params={"subject_id": "not-a-real-subject"},
    )
    assert response.status_code == 404


def test_no_error_for_learner_with_zero_mastery_state_rows(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["next_topic"]["band"] == "unknown"


def test_no_assessment_event_or_trace_side_effects(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    # A pre-existing MasteryState row so is_fallback/band paths aren't
    # trivially the zero-data case -- still must have zero side effects.
    db_session.add(
        MasteryState(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id="integers-and-operations",
            p_mastery=0.5,
            update_count=1,
        )
    )
    db_session.commit()

    client = TestClient(app)
    with patch("src.observability.tracing.flush_traces") as mock_flush:
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
            params={"subject_id": algebra_subject.subject_id},
        )

    assert response.status_code == 200, response.text
    assert db_session.query(AssessmentEvent).count() == 0
    mock_flush.assert_not_called()
