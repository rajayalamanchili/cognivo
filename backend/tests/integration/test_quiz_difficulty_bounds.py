"""Integration test (SC-003, User Story 3), T032.

A scripted all-correct run reaches and holds at `hard`; a scripted
all-incorrect run reaches and holds at `easy`; neither errors nor
requests an undefined level. Also asserts the logged
`quiz_difficulty_adjusted` event's `held_at_bound` field is `true` for
the decision(s) at the bound (FR-009, analysis finding C2) -- no new
production code, this is verification of behavior already built into
`next_difficulty` in Foundational.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def _answer_n_times(client: TestClient, quiz: dict, *, correct: bool, count: int) -> list[str]:
    """Answers `count` questions in a row, all `correct`, returning the
    difficulty of each subsequent question generated."""
    difficulties = []
    question_id = quiz["question"]["question_id"]
    for i in range(count):
        answer = client.post(
            f"/api/questions/{question_id}/answer",
            json={"response": 0 if correct else 1},
        )
        assert answer.status_code == 200, answer.text

        if i == count - 1:
            break

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        difficulties.append(body["question"]["difficulty"])
        question_id = body["question"]["question_id"]

    return difficulties


def test_all_correct_run_reaches_and_holds_at_hard(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 8}
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    assert quiz["question"]["difficulty"] == "easy"

    difficulties = _answer_n_times(client, quiz, correct=True, count=7)
    # easy -> easy(1 correct) -> medium(2) -> medium(1) -> hard(2) ->
    # hard(1) -> hard(held).
    assert difficulties == ["easy", "medium", "medium", "hard", "hard", "hard"]

    quiz_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .all()
    )
    assert any(event.payload["held_at_bound"] for event in quiz_events)


def test_all_incorrect_run_reaches_and_holds_at_easy(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 4}
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    assert quiz["question"]["difficulty"] == "easy"

    difficulties = _answer_n_times(client, quiz, correct=False, count=3)
    # easy -> easy(1 incorrect) -> easy(held, 2 incorrect).
    assert difficulties == ["easy", "easy"]

    question_id = quiz["question"]["question_id"]
    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question_id),
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["new_band"] == "easy"
    assert events[0].payload["held_at_bound"] is False  # only 1 incorrect so far, no threshold yet

    quiz_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        )
        .all()
    )
    assert any(event.payload["held_at_bound"] for event in quiz_events)
