"""Integration test: read-aloud eligibility and usage logging (spec 019
FR-001/FR-003/FR-011/FR-012/SC-001/SC-007, research.md Decisions 1-2).

`read_aloud_eligible` on the next-question response is derived live
from `GradeProgress.unlocked_grade`, never a separately stored copy of
grade -- this test manipulates that row directly rather than assuming
any particular subject's real starting grade, since `algebra-1`'s own
grade bands (Milestone 15) start well above grade 2.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.grade_progress import GradeProgress
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def _place_and_answer_once(client, db_session, demo_learner, algebra_subject, *, body: dict):
    """Wraps every generation-triggering call (`placement/start` and
    `next-question`) in `patch_generation()` -- this CI environment
    deliberately withholds a real `ANTHROPIC_API_KEY` from the `pytest`
    job (backend-tests.yml: "every test exercising this path mocks
    `_run_agent_once`"), so a local sandbox with working LLM credentials
    can mask a missing mock here that only surfaces in CI."""
    with patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        questions = start.json()["questions"]
        answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
        submit = client.post(
            f"/api/placement/{start.json()['placement_session_id']}/submit",
            json={"answers": answers},
        )
        assert submit.status_code == 200, submit.text

        next_question = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )
        assert next_question.status_code == 200, next_question.text
        question = next_question.json()

    answer = client.post(f"/api/questions/{question['question_id']}/answer", json=body)
    assert answer.status_code == 200, answer.text
    return question, answer


def test_read_aloud_ineligible_above_grade_two(db_session, demo_learner, algebra_subject):
    """`algebra-1`'s own grade bands start at 6+ (Milestone 15) -- a
    freshly-placed learner is not read-aloud eligible."""
    from src.api.main import app

    client = TestClient(app)
    question, _ = _place_and_answer_once(
        client, db_session, demo_learner, algebra_subject, body={"response": 1}
    )
    assert question["read_aloud_eligible"] is False


def test_read_aloud_eligible_at_grade_two(db_session, demo_learner, algebra_subject):
    """Exercises `resolve_read_aloud_eligible` directly against a
    manually-seeded `GradeProgress` row, rather than driving the full
    placement/next-question pipeline: `algebra-1`'s own grade bands
    floor at 6 (Milestone 15's `determine_starting_grade` never places a
    real learner below a subject's declared floor), so a real
    unlocked_grade of 2 cannot occur for this subject -- forcing it
    through the live sequencing path would exercise an unrelated,
    pre-existing edge case in grade-eligible topic ranking rather than
    this feature's own logic."""
    from src.services.mediation.read_aloud import resolve_read_aloud_eligible

    db_session.add(
        GradeProgress(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=2,
        )
    )
    db_session.commit()

    assert (
        resolve_read_aloud_eligible(
            db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
        )
        is True
    )


def test_read_aloud_used_is_recorded_on_the_answer_event(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    question, _ = _place_and_answer_once(
        client,
        db_session,
        demo_learner,
        algebra_subject,
        body={"response": 1, "read_aloud_used": True},
    )

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .first()
    )
    assert event is not None
    assert event.payload["read_aloud_used"] is True


def test_read_aloud_used_defaults_to_false_when_omitted(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    question, _ = _place_and_answer_once(
        client, db_session, demo_learner, algebra_subject, body={"response": 1}
    )

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .first()
    )
    assert event is not None
    assert event.payload["read_aloud_used"] is False


def test_placement_submit_records_read_aloud_used_per_answer(
    db_session, demo_learner, algebra_subject
):
    """Code-review finding: unlike the practice/quiz answer path, the
    placement submit route never carried a `read_aloud_used` fact at
    all -- SC-007 claims 100% reconstructability of read-aloud usage
    for a given question, not just quiz/practice questions."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    assert len(questions) >= 2

    answers = [
        {"question_id": questions[0]["question_id"], "response": 1, "read_aloud_used": True},
        {"question_id": questions[1]["question_id"], "response": 1},
    ]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text

    def _event_for(question_id):
        return (
            db_session.query(AssessmentEvent)
            .filter(
                AssessmentEvent.question_id == question_id,
                AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            )
            .first()
        )

    used_event = _event_for(questions[0]["question_id"])
    assert used_event is not None
    assert used_event.payload["read_aloud_used"] is True

    omitted_event = _event_for(questions[1]["question_id"])
    assert omitted_event is not None
    assert omitted_event.payload["read_aloud_used"] is False
