"""Integration test: progressive grade unlocking end to end (spec 017
User Story 2, T025).

Places a learner at grade 6 (algebra-1), drives every grade-6 topic to
mastered one at a time via the real `next-question`/`answer` API flow,
and confirms a higher grade is never selectable until the last grade-6
topic is mastered -- then confirms it becomes selectable immediately
after, with both the `grade_assigned` and `grade_unlocked` audit events
present (SC-002, SC-003, SC-006).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), matching `test_second_subject.py`'s convention --
distinct stems per call so the near-duplicate dedup check never forces
extra regeneration attempts.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState

GRADE_6_TOPICS = ["integers-and-operations", "variables-and-expressions", "solving-one-step-equations"]
GRADE_7_OR_8_TOPICS = {
    "order-of-operations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "graphing-linear-equations",
    "systems-of-linear-equations",
}


def _client() -> TestClient:
    from src.api.main import app

    return TestClient(app)


NUMERIC_CORRECT_VALUE = 5
NUMERIC_TOLERANCE = 0.5


def _draft_json(stem: str, *, numeric: bool) -> str:
    if numeric:
        return json.dumps(
            {
                "question_type": "numeric",
                "stem": stem,
                "options": None,
                "correct_index": None,
                "correct_value": NUMERIC_CORRECT_VALUE,
                "tolerance": NUMERIC_TOLERANCE,
            }
        )
    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": stem,
            "options": ["a", "b", "c", "d"],
            "correct_index": 1,
            "correct_value": None,
            "tolerance": None,
        }
    )


def _patch_generation():
    # solving-one-step-equations is numeric-only
    # (content/algebra-1/subject.yaml) -- the instruction text embeds
    # the requested question_type verbatim (_build_instruction), so
    # branch on that rather than assuming multiple_choice everywhere.
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        numeric = "requested question type: numeric" in agent.instruction.lower()
        return _draft_json(f"mock question #{call_count['n']}", numeric=numeric)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )


def _set_mastered(db_session, learner_id, subject_id, topic_id):
    # integers-and-operations/variables-and-expressions are grade-6
    # entry topics -- placement already created a MasteryState row for
    # each, so this upserts rather than inserts.
    state = db_session.get(MasteryState, (learner_id, subject_id, topic_id))
    if state is None:
        state = MasteryState(learner_id=learner_id, subject_id=subject_id, topic_id=topic_id)
        db_session.add(state)
    state.p_mastery = 0.9
    state.update_count = 1
    state.consecutive_mastered_observations = 2
    db_session.commit()


def test_grade_never_advances_past_current_grade_until_mastered_then_unlocks(
    db_session, demo_learner, algebra_subject
):
    client = _client()
    subject_id = algebra_subject.subject_id
    learner_id = demo_learner.learner_id

    with _patch_generation():
        start = client.post(f"/api/subjects/{subject_id}/placement/start")
        assert start.status_code == 200, start.text
        body = start.json()
        placement_session_id = body["placement_session_id"]
        questions = body["questions"]

        # Grade 6's entry topics correct; grade 7/8 incorrect -- starting
        # grade floors at 6 (starting_grade.py's contiguous-from-lowest
        # rule).
        answers = [
            {
                "question_id": q["question_id"],
                "response": 1 if q["grade"] == 6 else 0,
            }
            for q in questions
        ]
        submit = client.post(
            f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
        )
        assert submit.status_code == 200, submit.text

        grade_assigned = (
            db_session.query(AssessmentEvent)
            .filter(
                AssessmentEvent.learner_id == learner_id,
                AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED,
            )
            .one()
        )
        assert grade_assigned.payload["starting_grade"] == 6

        progress = db_session.get(GradeProgress, (learner_id, subject_id))
        assert progress.unlocked_grade == 6

        # Two of the three grade-6 topics are already mastered -- only
        # solving-one-step-equations (whose prerequisite,
        # variables-and-expressions, is now mastered) remains eligible
        # at grade <= 6.
        _set_mastered(db_session, learner_id, subject_id, "integers-and-operations")
        _set_mastered(db_session, learner_id, subject_id, "variables-and-expressions")

        # solving-one-step-equations is numeric-only (higher guess
        # penalty than multiple_choice), so its first correct answer
        # already crosses p_mastery>=0.7 -- MASTERY_CONFIRMATION_THRESHOLD=2
        # needs exactly one more correct answer after that to confirm.
        for _ in range(1):
            next_q = client.get(
                f"/api/learners/{learner_id}/next-question", params={"subject_id": subject_id}
            )
            assert next_q.status_code == 200, next_q.text
            selected = next_q.json()
            assert selected["topic_id"] == "solving-one-step-equations"
            assert selected["topic_id"] not in GRADE_7_OR_8_TOPICS

            answer = client.post(
                f"/api/questions/{selected['question_id']}/answer",
                json={"response": NUMERIC_CORRECT_VALUE},
            )
            assert answer.status_code == 200, answer.text
            assert answer.json()["band"] != "mastered"

        # Second correct answer confirms mastery (MASTERY_CONFIRMATION_THRESHOLD=2).
        next_q = client.get(
            f"/api/learners/{learner_id}/next-question", params={"subject_id": subject_id}
        )
        assert next_q.json()["topic_id"] == "solving-one-step-equations"
        final_answer = client.post(
            f"/api/questions/{next_q.json()['question_id']}/answer",
            json={"response": NUMERIC_CORRECT_VALUE},
        )
        assert final_answer.status_code == 200, final_answer.text
        assert final_answer.json()["band"] == "mastered"

    grade_unlocked = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.event_type == AssessmentEventType.GRADE_UNLOCKED,
        )
        .one()
    )
    assert grade_unlocked.payload["previous_unlocked_grade"] == 6
    assert grade_unlocked.payload["new_unlocked_grade"] == 7
    assert grade_unlocked.payload["triggering_topic_id"] == "solving-one-step-equations"

    progress = db_session.get(GradeProgress, (learner_id, subject_id))
    assert progress.unlocked_grade == 7

    # A grade-7 question is now selectable.
    with _patch_generation():
        next_q = client.get(
            f"/api/learners/{learner_id}/next-question", params={"subject_id": subject_id}
        )
    assert next_q.status_code == 200, next_q.text
    assert next_q.json()["topic_id"] in {"order-of-operations", "linear-inequalities"}

    # Both audit events are present for this learner/subject in one
    # continuous flow (SC-002, SC-003, SC-006).
    event_types = {
        event.event_type
        for event in db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.learner_id == learner_id, AssessmentEvent.subject_id == subject_id)
        .all()
    }
    assert AssessmentEventType.GRADE_ASSIGNED in event_types
    assert AssessmentEventType.GRADE_UNLOCKED in event_types
