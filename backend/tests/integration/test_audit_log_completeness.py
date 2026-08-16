"""Integration test: full audit-log completeness for a
placement-through-first-question session (SC-006), T057.

Confirms one `AssessmentEvent` row exists per placement question shown,
per answer submitted, per mastery update, and per next-topic selection --
and that each row's `payload` carries enough detail to reconstruct the
decision (Constitution Principle V's "why was I shown this" / "why was
this marked wrong").

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), same as test_placement_determinism.py and
test_next_question_variety.py -- this test is about the audit trail
around generation, not generation itself.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType


def _draft_json(stem: str) -> str:
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


def test_audit_log_completeness_for_placement_through_first_question(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        return _draft_json(f"audit-log test question #{call_count['n']}")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        placement_questions = start.json()["questions"]

        answers = [{"question_id": q["question_id"], "response": 1} for q in placement_questions]
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

        answer = client.post(
            f"/api/questions/{next_question.json()['question_id']}/answer",
            json={"response": 1},
        )
        assert answer.status_code == 200, answer.text

    events = db_session.query(AssessmentEvent).filter(
        AssessmentEvent.learner_id == demo_learner.learner_id
    ).all()
    by_type: dict[AssessmentEventType, list[AssessmentEvent]] = {}
    for event in events:
        by_type.setdefault(event.event_type, []).append(event)

    num_placement_questions = len(placement_questions)

    # One row per placement question shown.
    assert len(by_type.get(AssessmentEventType.PLACEMENT_QUESTION_SHOWN, [])) == (
        num_placement_questions
    )
    # One row per answer submitted -- placement answers plus the one
    # next-question answer.
    assert len(by_type.get(AssessmentEventType.ANSWER_SUBMITTED, [])) == (
        num_placement_questions + 1
    )
    # One row per mastery update -- same count as answers submitted,
    # since every graded answer triggers exactly one BKT update.
    assert len(by_type.get(AssessmentEventType.MASTERY_UPDATED, [])) == (
        num_placement_questions + 1
    )
    # One row per next-topic selection -- exactly the one next-question
    # request made above.
    assert len(by_type.get(AssessmentEventType.NEXT_TOPIC_SELECTED, [])) == 1

    # Every row carries enough payload detail to reconstruct the
    # decision -- not just an empty/placeholder payload.
    for event in by_type[AssessmentEventType.PLACEMENT_QUESTION_SHOWN]:
        assert event.payload["placement_session_id"]
        assert event.payload["difficulty"]

    for event in by_type[AssessmentEventType.ANSWER_SUBMITTED]:
        assert "response" in event.payload
        assert "correct" in event.payload

    for event in by_type[AssessmentEventType.MASTERY_UPDATED]:
        assert "posterior_p_mastery" in event.payload
        assert "answer_correct" in event.payload
        assert "bkt_params_used" in event.payload

    for event in by_type[AssessmentEventType.NEXT_TOPIC_SELECTED]:
        assert "candidate_topics_considered" in event.payload
        assert event.payload["chosen_topic"]
        assert "is_fallback" in event.payload
