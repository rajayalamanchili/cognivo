"""Integration test (SC-002, User Story 2), T030.

Complete a multi-question quiz, confirm every quiz-answered question
appears in `AssessmentEvent` history (`ANSWER_SUBMITTED`,
`MASTERY_UPDATED`) and `MasteryState` reflects it via the same
`GET /mastery-state` read path used elsewhere on the platform -- no new
production code, this is verification that User Story 1's reused,
unmodified `answer_question` mechanism already guarantees this by
construction (research.md §4).
"""

import uuid

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_every_quiz_answered_question_updates_mastery_state(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question_count = 3
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": question_count},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    question_id = quiz["question"]["question_id"]

    answered_question_ids = []
    for i in range(question_count):
        answer = client.post(
            f"/api/questions/{question_id}/answer", json={"response": i % 4}
        )
        assert answer.status_code == 200, answer.text
        answered_question_ids.append(question_id)

        if i == question_count - 1:
            break

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        question_id = next_q.json()["question"]["question_id"]

    # Every quiz-answered question appears in the regular assessment-
    # event history, via the exact same mechanism a non-quiz question
    # already uses.
    for qid in answered_question_ids:
        answer_events = (
            db_session.query(AssessmentEvent)
            .filter(
                AssessmentEvent.question_id == uuid.UUID(qid),
                AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            )
            .count()
        )
        assert answer_events == 1
        mastery_events = (
            db_session.query(AssessmentEvent)
            .filter(
                AssessmentEvent.question_id == uuid.UUID(qid),
                AssessmentEvent.event_type == AssessmentEventType.MASTERY_UPDATED,
            )
            .count()
        )
        assert mastery_events == 1

    # MasteryState reflects it via the same read path GET /mastery-state
    # already uses elsewhere on the platform (e.g. the learner dashboard).
    mastery_response = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert mastery_response.status_code == 200, mastery_response.text
    topics = {t["topic_id"]: t for t in mastery_response.json()["topics"]}
    assert topics[_ENTRY_TOPIC]["status"] == "scored"
    assert topics[_ENTRY_TOPIC]["p_mastery"] is not None
