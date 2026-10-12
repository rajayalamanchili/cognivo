"""Integration test: 5 consecutive next-question requests -- no two
text-identical/near-duplicate questions, 100% correctly topic-scoped
(SC-002), T040.

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`) with a distinct stem per call, so this test
exercises the real dedup-check + persistence path (FR-008) without
depending on a live LLM call.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.generated_question import GeneratedQuestion
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.services.dedup.checker import is_near_duplicate

# Mirrors free_text_helpers.py's `_OTHER_ALGEBRA_TOPIC_IDS` pattern --
# mastering every other algebra-1 topic leaves `_TARGET_TOPIC_ID` (an
# entry topic, no prerequisite) the lowest-mastery, always-eligible
# pick, so repeated `next-question` calls keep landing on the same
# topic (bug-fix amendment, 2026-10-12's test needs this; the original
# SC-002 test above doesn't pin a topic since it only needs distinct
# stems, not same-topic dedup history).
_TARGET_TOPIC_ID = "integers-and-operations"
_OTHER_ALGEBRA_TOPIC_IDS = [
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "systems-of-linear-equations",
    "graphing-linear-equations",
]

# Same phrasing template, different numbers -- the false-positive
# pattern a raw-text difflib check (0.87-0.94 similarity) flagged as
# near-duplicate (spec 001 FR-008/SC-002 Clarifications, 2026-10-12).
_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS = [
    "Solve for x: (x - 3)(x + 7) = 0",
    "Solve for x: (x - 2)(x + 5) = 0",
    "Solve for x: (x + 4)(x - 9) = 0",
]


def _draft_json(stem: str, *, correct_index: int = 1) -> str:
    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": stem,
            "options": ["a", "b", "c", "d"],
            "correct_index": correct_index,
            "correct_value": None,
            "tolerance": None,
        }
    )


def test_five_consecutive_next_questions_are_distinct_and_topic_scoped(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        return _draft_json(f"unique generated question #{call_count['n']}")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        questions = start.json()["questions"]
        answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
        submit = client.post(
            f"/api/placement/{start.json()['placement_session_id']}/submit",
            json={"answers": answers},
        )
        assert submit.status_code == 200, submit.text

        results = []
        for _ in range(5):
            response = client.get(
                f"/api/learners/{demo_learner.learner_id}/next-question",
                params={"subject_id": algebra_subject.subject_id},
            )
            assert response.status_code == 200, response.text
            results.append(response.json())

    stems = [r["stem"] for r in results]
    assert len(set(stems)) == len(stems), f"expected all-distinct stems, got {stems}"

    valid_topic_ids = {topic.topic_id for topic in algebra_subject.topics}
    for result in results:
        assert result["topic_id"] in valid_topic_ids
        assert result["difficulty"] in ("easy", "medium", "hard")


def test_same_template_different_numbers_not_near_duplicate_in_practice(
    db_session, demo_learner, algebra_subject
):
    """spec 001 FR-008/SC-002, Clarifications 2026-10-12: the Milestone 1
    practice path shares `is_near_duplicate` with the quiz path -- same
    fix, same false-positive pattern (test_quiz_no_duplicates.py's
    regression test covers the quiz side of this)."""
    from src.api.main import app

    client = TestClient(app)

    db_session.merge(
        GradeProgress(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=8,
        )
    )
    for topic_id in _OTHER_ALGEBRA_TOPIC_IDS:
        db_session.merge(
            MasteryState(
                learner_id=demo_learner.learner_id,
                subject_id=algebra_subject.subject_id,
                topic_id=topic_id,
                p_mastery=0.9,
                update_count=2,
                consecutive_mastered_observations=2,
            )
        )
    db_session.commit()

    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        stem = _SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS[
            call_count["n"] % len(_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS)
        ]
        call_count["n"] += 1
        return _draft_json(stem, correct_index=1)

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        for _ in range(len(_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS)):
            response = client.get(
                f"/api/learners/{demo_learner.learner_id}/next-question",
                params={"subject_id": algebra_subject.subject_id},
            )
            assert response.status_code == 200, response.text
            question_id = response.json()["question_id"]
            # Wrong answer every time -- keeps the target topic's
            # mastery low so it stays the sole eligible pick throughout.
            answer = client.post(
                f"/api/questions/{question_id}/answer", json={"response": 0}
            )
            assert answer.status_code == 200, answer.text

    rows = [
        (row.stem, row.stem_embedding)
        for row in db_session.query(GeneratedQuestion)
        .filter(
            GeneratedQuestion.learner_id == demo_learner.learner_id,
            GeneratedQuestion.topic_id == _TARGET_TOPIC_ID,
        )
        .order_by(GeneratedQuestion.generated_at)
        .all()
    ]
    assert len(rows) == len(_SAME_TEMPLATE_DIFFERENT_NUMBER_STEMS), (
        f"expected every question to land on {_TARGET_TOPIC_ID!r}, got {rows}"
    )
    for i, (_stem, embedding) in enumerate(rows):
        assert not is_near_duplicate(
            embedding, rows[:i]
        ), f"stem #{i} is a near-duplicate: {rows[i][0]!r}"
