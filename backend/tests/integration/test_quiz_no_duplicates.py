"""Integration test: zero near-duplicates within one quiz session
(SC-004), T027. Bug-fix amendment, 2026-10-12: also covers the
same-template/different-number false-positive case that previously made
single-topic quizzes end early after 1 question (spec.md FR-008/SC-004
Clarifications).

Runs a single-topic quiz with `question_count` greater than Milestone
1's 5-question default lookback, confirming no two questions in the
session are near-duplicates -- the dedup lookback is widened to the
quiz's own `question_count` (research.md §3), not capped at 5.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.generated_question import GeneratedQuestion
from src.services.dedup.checker import DEFAULT_LOOKBACK, is_near_duplicate
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"

# Same phrasing template, different numbers -- the false-positive
# pattern a raw-text difflib check (0.87-0.94 similarity) flagged as
# near-duplicate, but which the embedding-based check must not.
_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS = [
    "Solve for x: (x - 3)(x + 7) = 0",
    "Solve for x: (x - 2)(x + 5) = 0",
    "Solve for x: (x + 4)(x - 9) = 0",
    "Solve for x: (x - 1)(x + 6) = 0",
    "Solve for x: (x + 2)(x - 8) = 0",
]


def test_zero_near_duplicates_across_a_quiz_longer_than_the_default_lookback(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    question_count = DEFAULT_LOOKBACK + 3
    client = TestClient(app)

    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": question_count},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    question_id = quiz["question"]["question_id"]

    for i in range(question_count):
        answer = client.post(
            f"/api/questions/{question_id}/answer", json={"response": i % 4}
        )
        assert answer.status_code == 200, answer.text

        if i == question_count - 1:
            break

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        assert body["status"] == "in_progress"
        question_id = body["question"]["question_id"]

    rows = [
        (row.stem, row.stem_embedding)
        for row in db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == uuid.UUID(quiz["quiz_session_id"]))
        .order_by(GeneratedQuestion.generated_at)
        .all()
    ]
    assert len(rows) == question_count

    for i, (stem, embedding) in enumerate(rows):
        assert not is_near_duplicate(
            stem, embedding, rows[:i]
        ), f"stem #{i} is a near-duplicate: {rows[i][0]!r}"


def test_same_template_different_numbers_does_not_end_early(db_session, demo_learner, algebra_subject):
    """Reproduces the original live bug directly (spec.md Clarifications,
    2026-10-12): a single-topic, 5-question quiz where every question
    shares a phrasing template and differs only in its numbers must
    complete all 5 questions, never `ended_early` -- the raw-text
    difflib check this replaces scored these pairs 0.87-0.94 similarity,
    over its 0.85 threshold, exhausting dedup retries after 1 question."""
    from src.api.main import app

    question_count = len(_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS)
    client = TestClient(app)

    with patch_generation(stems=_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS):
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": question_count},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    question_id = quiz["question"]["question_id"]

    for i in range(question_count):
        answer = client.post(f"/api/questions/{question_id}/answer", json={"response": i % 4})
        assert answer.status_code == 200, answer.text

        if i == question_count - 1:
            break

        with patch_generation(stems=_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS):
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        assert body["status"] == "in_progress", (
            f"quiz ended early at question {i + 1} of {question_count} -- "
            "same-template/different-number stems were wrongly treated as near-duplicates"
        )
        question_id = body["question"]["question_id"]

    final = client.get(f"/api/quizzes/{quiz['quiz_session_id']}")
    assert final.json()["status"] == "completed"
