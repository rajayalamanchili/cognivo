"""Integration tests: placement skip endpoint (spec 017 FR-006/FR-007/
FR-008, User Story 3, T029).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. Question generation is mocked at the LLM-call boundary
(`_run_agent_once`). Unlike other placement tests, this file's mock is
type-aware: a skip's replacement topic can be `solving-one-step-
equations` (grade 6, `preferred_question_types: [numeric]`) -- the only
grade-6 topic left once both grade-6 entry topics are already shown at
`start_placement` -- so a fixed multiple_choice-only draft isn't enough
here.
"""

import datetime
import json
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion

_MULTIPLE_CHOICE_DRAFT = {
    "question_type": "multiple_choice",
    "stem": "mock multiple_choice question",
    "options": ["a", "b", "c", "d"],
    "correct_index": 1,
    "correct_value": None,
    "tolerance": None,
}

_NUMERIC_DRAFT = {
    "question_type": "numeric",
    "stem": "mock numeric question",
    "options": None,
    "correct_index": None,
    "correct_value": 4.0,
    "tolerance": 0.005,
}


def _patch_generation():
    async def _fake_run_agent_once(agent, session_service):
        if "Requested question type: numeric" in agent.instruction:
            return json.dumps(_NUMERIC_DRAFT)
        return json.dumps(_MULTIPLE_CHOICE_DRAFT)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )


def _client() -> TestClient:
    from src.api.main import app

    return TestClient(app)


def _start(client, subject_id: str) -> dict:
    with _patch_generation():
        response = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert response.status_code == 200, response.text
    return response.json()


def _question_by_topic(questions: list[dict], topic_id: str) -> dict:
    return next(q for q in questions if q["topic_id"] == topic_id)


def test_skip_above_interim_level_returns_a_lower_grade_replacement(
    demo_learner, algebra_subject
):
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    order_of_operations = _question_by_topic(body["questions"], "order-of-operations")
    assert order_of_operations["grade"] == 7  # interim level is 6 (floor, no answers yet)

    with _patch_generation():
        response = client.post(
            f"/api/placement/{body['placement_session_id']}/skip",
            json={"question_id": order_of_operations["question_id"]},
        )

    assert response.status_code == 200, response.text
    replacement = response.json()["replacement_question"]
    assert replacement is not None
    assert replacement["grade"] <= 6
    assert replacement["topic_id"] not in {q["topic_id"] for q in body["questions"]}


def test_skip_at_or_below_interim_level_returns_422(demo_learner, algebra_subject):
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    grade_6_question = _question_by_topic(body["questions"], "integers-and-operations")

    response = client.post(
        f"/api/placement/{body['placement_session_id']}/skip",
        json={"question_id": grade_6_question["question_id"]},
    )

    assert response.status_code == 422


def test_skip_an_already_answered_question_returns_409(
    db_session, demo_learner, algebra_subject
):
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    order_of_operations = _question_by_topic(body["questions"], "order-of-operations")

    submit = client.post(
        f"/api/placement/{body['placement_session_id']}/submit",
        json={"answers": [{"question_id": order_of_operations["question_id"], "response": 1}]},
    )
    assert submit.status_code == 200, submit.text

    response = client.post(
        f"/api/placement/{body['placement_session_id']}/skip",
        json={"question_id": order_of_operations["question_id"]},
    )

    assert response.status_code == 409


def test_skip_against_ungraded_subject_returns_422(demo_learner, biology_subject):
    client = _client()
    body = _start(client, biology_subject.subject_id)
    question = body["questions"][0]

    response = client.post(
        f"/api/placement/{body['placement_session_id']}/skip",
        json={"question_id": question["question_id"]},
    )

    assert response.status_code == 422


def test_skip_records_placement_question_skipped_event(db_session, demo_learner, algebra_subject):
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    order_of_operations = _question_by_topic(body["questions"], "order-of-operations")

    with _patch_generation():
        response = client.post(
            f"/api/placement/{body['placement_session_id']}/skip",
            json={"question_id": order_of_operations["question_id"]},
        )
    replacement = response.json()["replacement_question"]

    event = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.PLACEMENT_QUESTION_SKIPPED)
        .one()
    )
    assert event.payload["skipped_question_id"] == order_of_operations["question_id"]
    assert event.payload["skipped_topic_id"] == "order-of-operations"
    assert event.payload["skipped_grade"] == 7
    assert event.payload["replacement_question_id"] == replacement["question_id"]
    assert event.payload["replacement_topic_id"] == replacement["topic_id"]
    assert event.payload["replacement_grade"] == replacement["grade"]
    assert event.payload["placement_session_id"] == body["placement_session_id"]


def test_skipped_question_topic_reports_unknown_after_submit(
    db_session, demo_learner, algebra_subject
):
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    questions = body["questions"]
    order_of_operations = _question_by_topic(questions, "order-of-operations")

    with _patch_generation():
        client.post(
            f"/api/placement/{body['placement_session_id']}/skip",
            json={"question_id": order_of_operations["question_id"]},
        )

    # Submit answers for every question except the skipped one.
    answers = [
        {"question_id": q["question_id"], "response": 1}
        for q in questions
        if q["question_id"] != order_of_operations["question_id"]
    ]
    submit = client.post(
        f"/api/placement/{body['placement_session_id']}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    mastery_by_topic = {entry["topic_id"]: entry for entry in submit.json()["mastery_state"]}
    assert mastery_by_topic["order-of-operations"]["status"] == "unknown"
    assert mastery_by_topic["order-of-operations"]["p_mastery"] is None


def test_skipping_every_above_level_question_still_lets_placement_terminate_validly(
    db_session, demo_learner, algebra_subject
):
    """FR-008: even once every lower-grade replacement topic is
    exhausted (no more topics left to serve), placement still completes
    with a valid starting grade rather than looping indefinitely."""
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    questions = body["questions"]
    placement_session_id = body["placement_session_id"]

    above_level_topic_ids = ["order-of-operations", "linear-inequalities", "systems-of-linear-equations"]
    skipped_question_ids = set()
    replacement_question_ids = set()
    for topic_id in above_level_topic_ids:
        question = _question_by_topic(questions, topic_id)
        skipped_question_ids.add(question["question_id"])
        with _patch_generation():
            response = client.post(
                f"/api/placement/{placement_session_id}/skip",
                json={"question_id": question["question_id"]},
            )
        assert response.status_code == 200, response.text
        replacement = response.json()["replacement_question"]
        if replacement is not None:
            replacement_question_ids.add(replacement["question_id"])

    # Only one grade-6 topic (solving-one-step-equations) was available
    # as a replacement -- the second and third skips get none.
    assert len(replacement_question_ids) == 1

    remaining_original = [q for q in questions if q["question_id"] not in skipped_question_ids]
    answers = [
        {"question_id": q["question_id"], "response": 1} for q in remaining_original
    ] + [{"question_id": qid, "response": 1} for qid in replacement_question_ids]

    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    event = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED)
        .one()
    )
    assert event.payload["starting_grade"] == 6


def _mark_topic_used(db_session, *, learner, subject_id, topic_id, grade, placement_session_id):
    """Simulate `topic_id` already having been served in this placement
    session (e.g. as an earlier skip-replacement) -- the skip endpoint's
    replacement query only cares that a `GeneratedQuestion` row exists
    for the topic under this `placement_session_id`, not its answer
    state."""
    db_session.add(
        GeneratedQuestion(
            learner_id=learner.learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            grade=grade,
            placement_session_id=placement_session_id,
            difficulty=DifficultyBand.EASY,
            question_type=QuestionType.NUMERIC,
            stem="filler",
            answer_key={"value": 1.0, "tolerance": 0.0},
            validation_status=ValidationStatus.VALID,
            shown_at=datetime.datetime.now(datetime.UTC),
        )
    )
    db_session.commit()


def test_skip_never_offers_a_free_text_replacement(db_session, demo_learner, algebra_subject):
    """A free_text topic (`graphing-linear-equations`) can never be
    graded by `grade_answer` (services/mastery/grading.py has no
    FREE_TEXT case) -- if it's the only remaining lower-grade candidate,
    the skip must return no replacement rather than one that would 500
    the eventual `submit_placement` call."""
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    questions = body["questions"]
    placement_session_id = uuid.UUID(body["placement_session_id"])

    # Exhaust every structured (non-free_text) grade<=7 topic other than
    # graphing-linear-equations, so it's the only remaining candidate.
    _mark_topic_used(
        db_session,
        learner=demo_learner,
        subject_id=algebra_subject.subject_id,
        topic_id="solving-one-step-equations",
        grade=6,
        placement_session_id=placement_session_id,
    )
    _mark_topic_used(
        db_session,
        learner=demo_learner,
        subject_id=algebra_subject.subject_id,
        topic_id="solving-multi-step-equations",
        grade=7,
        placement_session_id=placement_session_id,
    )

    # Raise the interim level to 7 by answering every grade 6/7 entry
    # topic correctly, leaving only the grade-8 question unanswered.
    grade_6_and_7_topics = {"integers-and-operations", "variables-and-expressions", "order-of-operations", "linear-inequalities"}
    answers = [
        {"question_id": q["question_id"], "response": 1}
        for q in questions
        if q["topic_id"] in grade_6_and_7_topics
    ]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    systems_question = _question_by_topic(questions, "systems-of-linear-equations")
    response = client.post(
        f"/api/placement/{placement_session_id}/skip",
        json={"question_id": systems_question["question_id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["replacement_question"] is None


def test_partial_submit_does_not_permanently_assign_a_starting_grade(
    db_session, demo_learner, algebra_subject
):
    """A `submit_placement` call that doesn't cover every non-skipped
    session question must not trigger the one-time starting-grade
    assignment -- otherwise a partial submission would permanently lock
    in a starting grade lower than the learner's answers actually
    support (no `GradeProgress` row exists yet to correct it)."""
    client = _client()
    body = _start(client, algebra_subject.subject_id)
    questions = body["questions"]
    placement_session_id = body["placement_session_id"]

    # Submit only one of the five questions -- the rest are neither
    # answered nor skipped.
    partial_answers = [{"question_id": questions[0]["question_id"], "response": 1}]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": partial_answers}
    )
    assert submit.status_code == 200, submit.text

    assert (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED)
        .first()
        is None
    )

    # Submitting the remaining questions completes the session and now
    # assigns a starting grade.
    remaining_answers = [
        {"question_id": q["question_id"], "response": 1}
        for q in questions[1:]
    ]
    submit2 = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": remaining_answers}
    )
    assert submit2.status_code == 200, submit2.text
    assert (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED)
        .one()
    )
