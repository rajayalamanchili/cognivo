"""Integration test: determinism check (SC-001), T026.

Replays an identical scripted answer sequence against a fresh quiz ten
times, confirming identical difficulty progression and final score
every run -- scoped to difficulty progression and score only, not
generated question *text* (SC-001, checklist review 2026-08-18).
"""

from fastapi.testclient import TestClient

from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"
_SCRIPT = [True, True, False, True, False, False]


def _run_scripted_quiz(client: TestClient) -> tuple[list[str], dict]:
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": len(_SCRIPT)},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()

    difficulty_progression = [quiz["question"]["difficulty"]]
    question_id = quiz["question"]["question_id"]

    for i, correct in enumerate(_SCRIPT):
        answer = client.post(
            f"/api/questions/{question_id}/answer", json={"response": 0 if correct else 1}
        )
        assert answer.status_code == 200, answer.text

        if i == len(_SCRIPT) - 1:
            break

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        difficulty_progression.append(body["question"]["difficulty"])
        question_id = body["question"]["question_id"]

    summary = client.get(f"/api/quizzes/{quiz['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    return difficulty_progression, summary.json()["score"]


def test_identical_answer_sequence_yields_identical_progression_and_score(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    results = [_run_scripted_quiz(client) for _ in range(10)]

    first_progression, first_score = results[0]
    for progression, score in results[1:]:
        assert progression == first_progression
        assert score == first_score
