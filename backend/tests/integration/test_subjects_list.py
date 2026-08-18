"""Integration test: `GET /api/subjects` (contracts/api.md, research.md
§4), T004.

Confirms both seeded subjects are returned ordered by `subject_id`,
that only `validated_at IS NOT NULL` subjects are included, and that
listing subjects has no `AssessmentEvent`/trace side effects -- it is a
pure read, matching the existing `GET /mastery-state` precedent.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.subject import Subject


def test_lists_both_seeded_subjects_ordered_by_subject_id(
    db_session, algebra_subject, biology_subject
):
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/subjects")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "subjects": [
            {"subject_id": "algebra-1", "display_name": algebra_subject.display_name},
            {"subject_id": "biology", "display_name": biology_subject.display_name},
        ]
    }


def test_excludes_unvalidated_subjects(db_session, algebra_subject, biology_subject):
    from src.api.main import app

    unvalidated = Subject(
        subject_id="chemistry",
        display_name="Chemistry",
        content_version="0.0.1",
        validated_at=None,
    )
    db_session.add(unvalidated)
    db_session.commit()

    client = TestClient(app)
    response = client.get("/api/subjects")

    assert response.status_code == 200, response.text
    subject_ids = [entry["subject_id"] for entry in response.json()["subjects"]]
    assert "chemistry" not in subject_ids
    assert subject_ids == ["algebra-1", "biology"]


def test_no_assessment_event_side_effects(db_session, algebra_subject, biology_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/subjects")

    assert response.status_code == 200, response.text
    assert db_session.query(AssessmentEvent).count() == 0
