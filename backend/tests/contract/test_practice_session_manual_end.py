"""Contract tests: `POST /api/practice-sessions/{id}/end` (spec 022
FR-010, contracts/api.md). No "untimed" 404 case -- every
`PracticeSession` row is timed by construction.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.practice_session import PracticeSession
from tests.integration.quiz_helpers import patch_generation


def _complete_placement(client: TestClient, subject_id: str) -> None:
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


def test_in_progress_session_ends_200(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(demo_learner.learner_id),
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text

    end = client.post(f"/api/practice-sessions/{start.json()['practice_session_id']}/end")
    assert end.status_code == 200, end.text
    assert end.json()["status"] == "ended_early"


def test_already_terminal_session_returns_409(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(demo_learner.learner_id),
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    practice_session_id = start.json()["practice_session_id"]

    first = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert first.status_code == 200, first.text

    second = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert second.status_code == 409, second.text


def test_manual_end_after_silent_deadline_records_timer_expired(
    db_session, demo_learner, algebra_subject
):
    """PR feedback: a manual "end now" arriving after the real deadline
    has already passed (but before anything else ran the lazy expiry
    check) must record `end_reason=timer_expired`, not
    `manually_ended_early` -- the route runs the expiry check first."""
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(demo_learner.learner_id),
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 900,
            },
        )
    assert start.status_code == 200, start.text
    practice_session_id = start.json()["practice_session_id"]

    session = db_session.get(PracticeSession, practice_session_id)
    session.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1000)
    db_session.commit()

    end = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert end.status_code == 409, end.text

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .one()
    )
    assert event.payload["end_reason"] == "timer_expired"
