"""Integration test: `GUARDIAN_MEDIATION_APPLIED` audit event (spec 019
FR-012/SC-007, data-model.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.grade_progress import GradeProgress
from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    login_guardian,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _start_attempt(client, db_session, subject, *, label, topic_id, unlocked_grade):
    instructor_email = f"tier-audit-instructor-{label}@example.com"
    guardian_email = f"tier-audit-guardian-{label}@example.com"

    register_instructor(client, instructor_email)
    roster_id, join_code = create_roster(client, subject_id=subject.subject_id)
    client.post("/api/auth/logout")

    guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name=f"Learner {label}"
    )
    join_response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert join_response.status_code == 201, join_response.text

    if unlocked_grade is not None:
        db_session.add(
            GradeProgress(
                learner_id=learner_id, subject_id=subject.subject_id, unlocked_grade=unlocked_grade
            )
        )
        db_session.commit()

    client.post("/api/auth/logout")
    login_instructor(client, instructor_email)
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[topic_id], learner_ids=[learner_id]
    )
    client.post("/api/auth/logout")

    login_guardian(client, guardian_email)
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    return start.json(), learner_id


@pytest.mark.parametrize(
    "unlocked_grade,expected_tier,expected_token_issued",
    [
        (2, "co_present", False),
        (4, "check_in", True),
        (7, "opt_in_nudges", True),
        (10, "independent", True),
    ],
)
def test_event_recorded_once_with_correct_tier_and_token_flag(
    client, db_session, algebra_subject, unlocked_grade, expected_tier, expected_token_issued
):
    label = f"grade-{unlocked_grade}"
    body, learner_id = _start_attempt(
        client,
        db_session,
        algebra_subject,
        label=label,
        topic_id=ENTRY_TOPIC,
        unlocked_grade=unlocked_grade,
    )

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.event_type == AssessmentEventType.GUARDIAN_MEDIATION_APPLIED,
        )
        .all()
    )
    assert len(events) == 1
    payload = events[0].payload
    assert payload["quiz_session_id"] == body["quiz_session_id"]
    assert payload["tier"] == expected_tier
    assert payload["handoff_token_issued"] is expected_token_issued
    assert (body["handoff_token"] is not None) is expected_token_issued


def test_ungraded_subject_records_a_null_tier_and_no_token(client, db_session, biology_subject):
    """FR-013: an ungraded subject (no `GradeProgress` row possible at
    all) still gets an honestly-logged `tier: null` event, not a
    silently-omitted one."""
    body, learner_id = _start_attempt(
        client,
        db_session,
        biology_subject,
        label="ungraded",
        topic_id="cell-structure-and-function",
        unlocked_grade=None,
    )

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.event_type == AssessmentEventType.GUARDIAN_MEDIATION_APPLIED,
        )
        .all()
    )
    assert len(events) == 1
    payload = events[0].payload
    assert payload["quiz_session_id"] == body["quiz_session_id"]
    assert payload["tier"] is None
    assert payload["handoff_token_issued"] is False
    assert body["handoff_token"] is None
