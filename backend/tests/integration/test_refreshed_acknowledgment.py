"""Integration test: `AnswerOut.refreshed` fires exactly on a below-to-
above `MASTERED` crossing (spec 025 User Story 4, FR-011/SC-005).

Seeds a fresh `GeneratedQuestion` for the same topic before each answer
and posts directly to `/api/questions/{id}/answer` -- bypassing
`/next-question`'s own topic-selection entirely, since once a topic is
mastered it leaves the eligible pool and a subsequent `/next-question`
call could move to a different topic, defeating a test that needs
several answers on the *same* topic to observe its mastery crossing.

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

import datetime
import uuid

from fastapi.testclient import TestClient

from src.models.enums import DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState

_TOPIC_ID = "integers-and-operations"


def _seed_question(db_session, *, learner_id, subject_id) -> uuid.UUID:
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=_TOPIC_ID,
        difficulty=DifficultyBand.MEDIUM,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="2 + 2?",
        options=["3", "4", "5", "6"],
        answer_key={"correct_index": 1},
        validation_status=ValidationStatus.VALID,
        shown_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(question)
    db_session.commit()
    return question.question_id


def _answer(client, question_id, *, correct: bool):
    response = client.post(
        f"/api/questions/{question_id}/answer", json={"response": 1 if correct else 0}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refreshed_true_only_on_below_to_above_mastered_crossing(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    learner_id, subject_id = demo_learner.learner_id, algebra_subject.subject_id

    def answer(*, correct: bool):
        question_id = _seed_question(db_session, learner_id=learner_id, subject_id=subject_id)
        return _answer(client, question_id, correct=correct)

    # Drive the topic up to mastered (3 correct crosses the 0.7 + 2-streak bar).
    result = None
    for _ in range(3):
        result = answer(correct=True)
    assert result["band"] == "mastered"

    # Re-answering an already-mastered topic: nothing to recover.
    reanswer = answer(correct=True)
    assert reanswer["refreshed"] is False

    # Force the topic back below threshold, then confirm no crossing yet.
    db_session.query(MasteryState).filter(
        MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id
    ).update({"p_mastery": 0.2, "consecutive_mastered_observations": 0})
    db_session.commit()

    stays_below = answer(correct=False)
    assert stays_below["band"] != "mastered"
    assert stays_below["refreshed"] is False

    # Drive it back up -- the crossing answer must report refreshed=True.
    crossing = None
    for _ in range(5):
        crossing = answer(correct=True)
        if crossing["band"] == "mastered":
            break
    assert crossing["band"] == "mastered"
    assert crossing["refreshed"] is True

    # Never re-shown on a later, unrelated request for the same topic.
    later = answer(correct=True)
    assert later["refreshed"] is False
