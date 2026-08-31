"""Integration test: engine works for a second subject with zero engine
code changes (SC-004, US3), T055.

Runs the full placement + next-question flow against `subject_id=biology`
-- a content artifact added entirely under `backend/content/biology/`,
with no edits to any file under `backend/src`. Mirrors
`test_placement_determinism.py`/`test_next_question_variety.py`'s
pattern of mocking the Assessment-Generation Agent's LLM call boundary
(`_run_agent_once`) so this test exercises the real placement, BKT
update, dedup, and next-topic-selection paths without depending on a
live LLM call.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.mastery_state import MasteryState

MASTERED_P = 0.9
MASTERED_CONSECUTIVE = 2


def _set_mastery(db_session, learner_id, subject_id, topic_id, *, p_mastery, consecutive=0):
    state = MasteryState(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        p_mastery=p_mastery,
        update_count=1,
        consecutive_mastered_observations=consecutive,
    )
    db_session.add(state)
    db_session.commit()
    return state


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


def test_placement_and_next_question_work_for_biology(db_session, demo_learner, biology_subject):
    from src.api.main import app

    client = TestClient(app)
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        return _draft_json(f"biology question #{call_count['n']}")

    valid_topic_ids = {topic.topic_id for topic in biology_subject.topics}
    entry_level_topic_ids = {
        topic.topic_id for topic in biology_subject.topics if topic.is_entry_level
    }

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        start = client.post(f"/api/subjects/{biology_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        placement_body = start.json()
        questions = placement_body["questions"]

        # Placement asks exactly one question per entry-level topic (FR-003).
        placement_topic_ids = {q["topic_id"] for q in questions}
        assert placement_topic_ids == entry_level_topic_ids

        answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
        submit = client.post(
            f"/api/placement/{placement_body['placement_session_id']}/submit",
            json={"answers": answers},
        )
        assert submit.status_code == 200, submit.text
        mastery_state = submit.json()["mastery_state"]
        assert {entry["topic_id"] for entry in mastery_state} <= valid_topic_ids
        assert any(entry["status"] == "scored" for entry in mastery_state)

        results = []
        for _ in range(5):
            response = client.get(
                f"/api/learners/{demo_learner.learner_id}/next-question",
                params={"subject_id": biology_subject.subject_id},
            )
            assert response.status_code == 200, response.text
            results.append(response.json())

    stems = [r["stem"] for r in results]
    assert len(set(stems)) == len(stems), f"expected all-distinct stems, got {stems}"
    for result in results:
        assert result["topic_id"] in valid_topic_ids
        assert result["difficulty"] in ("easy", "medium", "hard")


def test_biology_image_bearing_topic_matches_algebra_behavior(
    db_session, demo_learner, biology_subject
):
    """Image-based question generation and grading work identically for a
    second subject's image-bearing topic (FR-006, SC-004), added under
    `backend/content/biology/` alone -- no engine-code change required to
    make this pass (T024-T027).
    """
    from src.api.main import app

    client = TestClient(app)

    # Force selection of mendelian-genetics (same technique as
    # test_next_question_image.py for algebra-1's image-bearing topic):
    # master every other topic, including its own prerequisite, so it's
    # the sole prereq-satisfied, still-"unknown" topic left.
    for topic in biology_subject.topics:
        if topic.topic_id == "mendelian-genetics":
            continue
        _set_mastery(
            db_session,
            demo_learner.learner_id,
            biology_subject.subject_id,
            topic.topic_id,
            p_mastery=MASTERED_P,
            consecutive=MASTERED_CONSECUTIVE,
        )

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_draft_json("What is the offspring genotype ratio?")),
    ):
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": biology_subject.subject_id},
        )
        assert response.status_code == 200, response.text
        question = response.json()
        assert question["topic_id"] == "mendelian-genetics"
        assert question["image_url"] == "/content-images/biology/punnett-square-Aa-x-Aa.svg"
        assert question["image_alt_text"] == (
            "A 2x2 Punnett square for a cross between two Aa parents, with "
            "A and a alleles labeled on each axis and the four offspring "
            "genotypes AA, Aa, Aa, and aa filled in the grid cells."
        )

        correct = client.post(
            f"/api/questions/{question['question_id']}/answer", json={"response": 1}
        )
        assert correct.status_code == 200, correct.text
        body = correct.json()
        assert body["correct"] is True
        assert "image_url" not in body
        assert "image_alt_text" not in body
