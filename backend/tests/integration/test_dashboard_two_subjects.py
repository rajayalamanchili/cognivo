"""Integration test: the brand-new-learner "just getting started" state
falls out correctly from three already-existing endpoints for **both**
platform subjects, with zero engine-code branching between them
(SC-002, SC-005, User Story 4), T026.

Mirrors `test_second_subject.py`'s pattern of exercising a real
Postgres-backed content artifact end to end -- but for a learner with
zero `MasteryState` rows at all, driving `mastery-state`,
`recommendations`, and `topic-priority-preview` (this feature's own new
endpoint) rather than placement/next-question. The same assertion
helper runs against both `algebra-1` and `biology` in a loop: if either
subject needed a different code path here, that would itself be the
subject-id-keyed conditional Constitution Principle III/SC-005 forbid.
"""

from fastapi.testclient import TestClient


def _assert_just_getting_started(client: TestClient, learner_id, subject_id: str) -> None:
    mastery_response = client.get(
        f"/api/learners/{learner_id}/mastery-state", params={"subject_id": subject_id}
    )
    assert mastery_response.status_code == 200, mastery_response.text
    mastery_topics = mastery_response.json()["topics"]
    assert mastery_topics, f"{subject_id} has no topics at all"
    assert all(topic["status"] == "unknown" for topic in mastery_topics)
    assert all(topic["band"] is None for topic in mastery_topics)

    recommendations_response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert recommendations_response.status_code == 200, recommendations_response.text
    recommendations = recommendations_response.json()
    assert recommendations["data_sufficiency"] == "insufficient_data"
    assert recommendations["weak_areas"] == []
    all_topic_ids = {topic["topic_id"] for topic in mastery_topics}
    assert set(recommendations["not_yet_assessed_topic_ids"]) | set(
        recommendations["insufficient_data_topic_ids"]
    ) == all_topic_ids

    preview_response = client.get(
        f"/api/learners/{learner_id}/topic-priority-preview", params={"subject_id": subject_id}
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["next_topic"]["band"] == "unknown"


def test_brand_new_learner_just_getting_started_across_both_subjects(
    db_session, demo_learner, algebra_subject, biology_subject
):
    from src.api.main import app

    client = TestClient(app)

    for subject_id in (algebra_subject.subject_id, biology_subject.subject_id):
        _assert_just_getting_started(client, demo_learner.learner_id, subject_id)


def test_next_topic_is_an_entry_level_topic_for_both_subjects(
    db_session, demo_learner, algebra_subject, biology_subject
):
    from src.api.main import app

    client = TestClient(app)

    for subject in (algebra_subject, biology_subject):
        entry_level_topic_ids = {
            topic.topic_id for topic in subject.topics if topic.is_entry_level
        }
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/topic-priority-preview",
            params={"subject_id": subject.subject_id},
        )
        assert response.status_code == 200, response.text
        assert response.json()["next_topic"]["topic_id"] in entry_level_topic_ids
