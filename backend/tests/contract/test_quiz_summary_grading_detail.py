"""Contract test: `GET /api/quizzes/{id}` surfaces per-question grading
detail in the end-of-session summary (spec 025 User Story 3,
FR-009/FR-010, Clarifications).

Directly seeds `GeneratedQuestion`/`AssessmentEvent` rows for a free-text
answer rather than driving live LLM-backed free-text generation/grading
through the HTTP flow -- no existing quiz test exercises free-text
questions yet, and this is the exact style `test_next_topic_decay_
fallback.py` already established for exercising DB state directly
where the live flow would be needlessly complex to set up. A second,
MC-only test still drives the real HTTP start/answer/summary round
trip to prove response-model wiring end to end.

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime
import uuid

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_session import QuizSession, QuizSessionStatus
from tests.integration.quiz_helpers import patch_generation

_TOPIC_ID = "integers-and-operations"


def _seed_free_text_answer(db_session, *, learner_id, subject_id, quiz_session_id) -> uuid.UUID:
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=_TOPIC_ID,
        difficulty=DifficultyBand.MEDIUM,
        question_type=QuestionType.FREE_TEXT,
        stem="Explain why -3 + 5 = 2.",
        answer_key={"criteria": ["identifies sign", "computes magnitude"]},
        validation_status=ValidationStatus.VALID,
        shown_at=datetime.datetime.now(datetime.UTC),
        quiz_session_id=quiz_session_id,
    )
    db_session.add(question)
    db_session.flush()

    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            subject_id=subject_id,
            topic_id=_TOPIC_ID,
            question_id=question.question_id,
            payload={
                "response": "It moves 5 right then... partially correct.",
                "correct": False,
                "criteria_met": ["identifies sign"],
                "criteria_missed": ["computes magnitude"],
            },
        )
    )
    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.MASTERY_UPDATED,
            subject_id=subject_id,
            topic_id=_TOPIC_ID,
            question_id=question.question_id,
            payload={
                "prior_p_mastery": 0.3,
                "posterior_p_mastery": 0.25,
                "answer_correct": False,
                "bkt_params_used": {},
            },
        )
    )
    db_session.commit()
    return question.question_id


def test_summary_includes_per_question_criteria_for_a_free_text_answer(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_ids=[_TOPIC_ID],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
        started_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(quiz)
    db_session.commit()

    question_id = _seed_free_text_answer(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        quiz_session_id=quiz.quiz_session_id,
    )

    client = TestClient(app)
    response = client.get(f"/api/quizzes/{quiz.quiz_session_id}")
    assert response.status_code == 200, response.text
    body = response.json()

    results = body["per_question_results"]
    assert len(results) == 1
    entry = results[0]
    assert entry["question_id"] == str(question_id)
    assert entry["topic_id"] == _TOPIC_ID
    assert entry["correct"] is False
    assert entry["criteria_met"] == ["identifies sign"]
    assert entry["criteria_missed"] == ["computes magnitude"]
    assert entry["prior_p_mastery"] == 0.3
    assert entry["posterior_p_mastery"] == 0.25
    # data-model.md §3: band is not reconstructable from historical events.
    assert "band" not in entry


def test_summary_wires_real_mc_answers_through_the_live_http_flow(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_TOPIC_ID], "question_count": 1}
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]
    question_id = start.json()["question"]["question_id"]

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    results = summary.json()["per_question_results"]
    assert len(results) == 1
    assert results[0]["question_id"] == question_id
    assert isinstance(results[0]["correct"], bool)
    assert results[0]["criteria_met"] is None
    assert results[0]["criteria_missed"] is None
